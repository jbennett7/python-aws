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

    def create_vpc(self, cidr_block='10.0.0.0/16'):
        vpc_id = ec2().create_vpc(
            CidrBlock=cidr_block)['Vpc']['VpcId']
        sleep1()
        while ec2().describe_vpcs(
            VpcIds=[vpc_id])['Vpcs'][0]['State'] != 'available':
                sleep1()
        self.objs['vpc'] = vpc_id

    def create_subnets(self, stype='private', az_count=2):
        vpc_id, cidr_block = self.get_vpc()
        subnet_tag = {'Key': 'type', 'Value': stype}

        # only one internet gateway per vpc and
        # only created if public subnets exist.
        if stype == 'public' and 'igw' not in self.objs:
            self.objs['igw'] = ec2().create_internet_gateway()\
                ['InternetGateway']['InternetGatewayId']
            ec2().attach_internet_gateway(
                InternetGatewayId=self.objs['igw'],
                VpcId=self.objs['vpc'])

        # only one route table per subnet type for the vpc.
        if 'rtb' not in self.objs or \
            [rtb for rtb in ec2().describe_route_tables(
            RouteTableIds=self.objs['rtb'])['RouteTables'] \
            for t in rtb['Tags'] if t['Key'] == 'type' \
            and t['Value'] == stype] == []:
                rtb_id = ec2().create_route_table(
                    VpcId=self.objs['vpc'])['RouteTable']['RouteTableId']
                sleep1()
                self._tag_resources([rtb_id], [subnet_tag])
                self.objs.append_to_objs('rtb', rtb_id)
                if stype == 'public':
                    ec2().create_route(
                        DestinationCidrBlock='0.0.0.0/0',
                        GatewayId=self.objs['igw'],
                        RouteTableId=rtb_id)
                    sleep1()
                    self.objs.append_to_objs('route', 
                        {'rtb': rtb_id, 'destination_cidr': '0.0.0.0/0'})

        i=1 if stype == 'public' else 0
        cidr_partition = str(list(ip_network(cidr_block).subnets())[i])
        az_list = [az['ZoneName'] \
            for az in ec2().describe_availability_zones()\
            ['AvailabilityZones']][:az_count]
        for az in az_list:
            cidr_list = [s['CidrBlock'] for s in ec2().describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [self.objs['vpc']]}])['Subnets']]
            cidr = list(set([str(c) for c in \
                list(ip_network(cidr_partition).subnets(new_prefix=24))]) -
                set(cidr_list))
            cidr.sort()
            cidr = cidr[0]
            subnet_id = ec2().create_subnet(
                AvailabilityZone=az,
                CidrBlock=cidr,
                VpcId=self.objs['vpc'])['Subnet']['SubnetId']
            sleep1()
            while ec2().describe_subnets(
                SubnetIds=[subnet_id])['Subnets'][0]['State'] != 'available':
                    sleep1()
            self._tag_resources([subnet_id], [subnet_tag])
            self.objs.append_to_objs('subnet', subnet_id)
            ec2().associate_route_table(
                RouteTableId=rtb_id,
                SubnetId=subnet_id)

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
