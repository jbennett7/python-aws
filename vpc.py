from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

from utility import ec2, sleep1, sleep2, sleep3

import yaml
from ipaddress import ip_network

class Vpc(object):

    def __init__(self, obj_list):
            self.objs = obj_list

    def _tag_resources(self, resource_ids, tags):
        ec2().create_tags(
            Resources=resource_ids, Tags=tags)

    def _get_available_cidr_block(self):
        cidr_block = ec2().describe_vpcs(VpcIds=[self.objs['vpc']])['Vpcs'][0]['CidrBlock']
        subnet_list = ec2().describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [self.objs['vpc']]}])['Subnets']
        cidr_list = [c['CidrBlock'] for c in subnet_list]
        cidr = list(set([str(c) for c in list(ip_network(cidr_block).subnets(new_prefix=24))]) -
            set(cidr_list))
        cidr.sort()
        return cidr[0]

    def _get_next_az(self, affinity_group=0):
        az_dict = {a['ZoneName']: 0 for a in \
            ec2().describe_availability_zones()['AvailabilityZones']}
        for az in [a['AvailabilityZones'] for a in ec2().describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [self.objs['vpc']]} ])['Subnets']]:
                az_dict[az] = az_dict[az] + 1
        min_value = min(az_dict.values())
        return next(k for k, v in az_dict.items() if v == min_value)

    def create_vpc(self, cidr_block='10.0.0.0/16'):
        vpc_id = ec2().create_vpc(
            CidrBlock=cidr_block)['Vpc']['VpcId']
        sleep1()
        while ec2().describe_vpcs(
            VpcIds=[vpc_id])['Vpcs'][0]['State'] != 'available':
                sleep1()
        self.objs['vpc'] = vpc_id

    def create_subnet(self, affinity_group=0):
        subnet_tags = [
            { 'Key': 'affinity_group', 'Value':  str(affinity_group) }
        ]
        az = self._get_next_az(affinity_group)
        cidr = self._get_available_cidr_block()
        subnet_id = ec2().create_subnet(
            AvailabilityZone=az,
            CidrBlock=cidr,
            VpcId=self.objs['vpc'])['Subnet']['SubnetId']
        self.objs.append_to_objs('subnet', subnet_id)
        self._tag_resources([subnet_id], subnet_tags)
        if 'rtb' in self.objs:
            rtb_list = [rtb['RouteTableId'] for rtb in ec2().describe_route_tables(
                RouteTableIds=self.objs['rtb'],
                Filters=[{'Name': 'tag:affinity_group', 'Values': [str(affinity_group)]}])\
                ['RouteTables']]
            for r in rtb_list:
                ec2().associate_route_table(
                    RouteTableId=r,
                    SubnetId=subnet_id)

    def create_route_table(self, affinity_group=0):
        if len([rtb['RouteTableId'] for rtb in ec2().describe_route_tables(
            RouteTableIds=self.objs['rtb'],
            Filters=[{'Name': 'tag:affinity_group', 'Values': [str(affinity_group)]}])\
            ['RouteTables']]) > 0:
                return 0

        rt_tags = [
            {'Key': 'affinity_group', 'Value': str(affinity_group)}
        ]
        rtb_id = ec2().create_route_table(
            VpcId=self.objs['vpc'])['RouteTable']['RouteTableId']
        sleep1()
        self._tag_resources([rtb_id], rt_tags)
        self.objs.append_to_objs('rtb', rtb_id)
        if 'subnet' in self.objs:
            subnets = [s['SubnetId'] for s in ec2().describe_subnets(
                SubnetIds=self.objs['subnet'],
                Filters=[{'Name': 'tag:affinity_group', 'Values': [str(affinity_group)]}])\
                ['Subnets']]
            for s in subnets:
                ec2().associate_route_table(
                    RouteTableId=rtb_id,
                    SubnetId=s)

    def create_internet_gateway(self, affinity_group=0):
        igw_tags = [
            {'Key': 'affinity_group', 'Value': str(affinity_group)}
        ]
        self.objs['igw'] = ec2().create_internet_gateway()\
            ['InternetGateway']['InternetGatewayId']
        ec2().attach_internet_gateway(
            InternetGatewayId=self.objs['igw'],
            VpcId=self.objs['vpc'])
        rtb_ids = [rtb['RouteTableId'] for rtb in \
            ec2().describe_route_tables(RouteTableIds=self.objs['rtb'],
            Filters=[{'Name': 'key:affinity_group', 'Values': [str(affinity_group)]}])\
            ['RouteTables']]
        subnet_ids = [s['SubnetId'] for s in \
            ec2().describe_subnets(SubnetIds=self.objs['subnet'],
                Filters=[{'Name': 'Key:affinity_group', 'Values': [str(affinity_group)]}])\
                ['Subnets']]
        for rtb in rtb_ids:
            ec2().create_route(
                DestinationCidrBlock='0.0.0.0/0',
                GatewayId=self.objs['igw'],
                RouteTableId=rtb_id)

    def create_nat_gateway(self, subnet_id):
        eipalloc_id = ec2().allocate_address(Domain='vpc')['AllocationId']
        self.objs.append_to_objs('eipalloc', eipalloc_id)
        ngw_id = ec2().create_nat_gateway(
            AllocationId=eipalloc_id, SubnetId=subnet_id)['NatGateway']['NatGatewayId']
        print("Waiting for Nat Gateway to become available.")
        while ec2().describe_nat_gateways(NatGatewayIds=[ngw_id])\
            ['NatGateways'][0]['State'] != 'available':
                sleep3()
        self.objs.append_to_objs('nat_gateways', ngw_id)
        self._tag_resources([subnet_id],[
            {'Key': 'ngw_id', 'Value': ngw_id},
            {'Key': 'ip_allocation_id', 'Value': eipalloc_id}])
        rt = next(rt for rt in \
            ec2().describe_route_tables(RouteTableIds=self.objs['rtb'])\
            ['RouteTables'] for t in rt['Tags'] \
            if t['Key'] == 'type' and t['Value'] == 'private')

    def get_subnets(self, sub_type):
        try:
            return [s['SubnetId'] for s in \
                    ec2().describe_subnets(SubnetIds=self.objs['subnet'])['Subnets'] \
                    for t in s['Tags'] if t['Key'] == 'type' and t['Value'] == sub_type]
        except KeyError:
            return []

    def get_vpc(self):
        vpc = ec2().describe_vpcs(
            VpcIds=[self.objs['vpc']])['Vpcs'][0]
        return vpc['VpcId'], vpc['CidrBlock']

    def delete_nat_gateways(self):
        try:
            for ngw_id in self.objs['nat_gateways']:
                ec2().delete_nat_gateway(NatGatewayId=ngw_id)
            print("Waiting for NAT Gateways to delete.")
            while all(n != 'deleted' for n in [ngw['State'] for ngw in \
                ec2().describe_nat_gateways(NatGatewayIds=self.objs['nat_gateways'])\
                ['NatGateways']]):
                            sleep3()
            del(self.objs['nat_gateways'])
            return 0
        except KeyError:
            return -1

    def delete_ip_allocations(self):
        try:
            for eipalloc_id in self.objs['eipalloc']:
                ec2().release_address(
                    AllocationId=eipalloc_id)
            del(self.objs['eipalloc'])
            return 0
        except KeyError:
            return -1

    def delete_route_tables(self):
        for rt in ec2().describe_route_tables(RouteTableIds=self.objs['rtb'])['RouteTables']:
            main=False
            for association in rt['Associations']:
                if association['Main'] == True:
                    main=True
                    continue
                ec2().disassociate_route_table(
                    AssociationId=association['RouteTableAssociationId'])
            if main == False:
                ec2().delete_route_table(RouteTableId=rt['RouteTableId'])
        del(self.objs['rtb'])

    def delete_subnets(self):
        for subnet_id in self.objs['subnet']:
            ec2().delete_subnet(SubnetId=subnet_id)
        del(self.objs['subnet'])

    def delete_internet_gateway(self):
        try:
            igw_id = self.objs['igw']
            vpc_id = self.objs['vpc']
            ec2().detach_internet_gateway(
                InternetGatewayId=igw_id,
                VpcId=vpc_id)
            ec2().delete_internet_gateway(
                InternetGatewayId=igw_id)
            del(self.objs['igw'])
        except KeyError:
            return 0

    def delete_vpc(self):
        try:
            ec2().delete_vpc(
                VpcId=self.objs['vpc'])
            del(self.objs['vpc'])
        except KeyError:
            return 0

    def delete_all(self):
        self.delete_nat_gateways()
        self.delete_ip_allocations()
        self.delete_routes()
        self.delete_route_tables()
        self.delete_subnets()
        self.delete_internet_gateway()
        self.delete_vpc()
