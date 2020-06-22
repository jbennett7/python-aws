from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

from base import AwsBase

import yaml
from ipaddress import ip_network
from utility import ec2
from botocore.exceptions import ClientError

class AwsVpc(AwsBase):

    def __init__(self, path):
        super().__init__(path)

    def get_vpc_id(self):
        try:
            return self['Vpc']['VpcId']
        except Exception as e:
            print(e)

    def get_available_cidr_block(self):
        cidr_block = self['Vpc']['CidrBlock']
        try:
            used_cidrs = [s['CidrBlock'] for s in self['Subnets']]
        except KeyError:
            used_cidrs = []
        cidr = list(set([str(c) for c in \
            list(ip_network(cidr_block).subnets(new_prefix=24))]) - set(used_cidrs))
        cidr.sort()
        return cidr[0]

    def get_next_az(self, affinity_group=0):
        az_dict = {a['ZoneName']: 0 for a in \
            ec2().describe_availability_zones()['AvailabilityZones']}
        for az in [a['AvailabilityZone'] for a in ec2().describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [self.get_vpc_id()]} ])['Subnets']]:
                az_dict[az] = az_dict[az] + 1
        min_value = min(az_dict.values())
        return next(k for k, v in az_dict.items() if v == min_value)

    def get_af_subnets(self, affinity_group=0):
        return [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
            if t['Name'] == 'affinity_group' and t['Value'] == str(affinity_group)]

    def get_af_rtb(self, affinity_group=0):
        return next(rtb['RouteTableId'] for rtb in self['RouteTables'] for t in rtb['Tags'] \
            if t['Name'] == 'affinity_group' and t['Value'] == str(affinity_group))

    def create_vpc(self, cidr_block='10.0.0.0/16'):
        if 'Vpc' in self:
            return 0
        k, d = self.execute(ec2().create_vpc(CidrBlock=cidr_block))
        self[k] = d
        self.waiter(ec2().describe_vpcs(VpcIds=[d['VpcId']]), k)
        self.save()

    def create_route_table(self, affinity_group=0):
        rt_tags = [
            {'Key': 'affinity_group', 'Value': str(affinity_group)}
        ]
        k, d = self.execute(ec2().create_route_table(VpcId=self.get_vpc_id()))
        k = 'RouteTables'
        self.append_to_objs(k, d)
        self.waiter(ec2().describe_route_tables(RouteTableIds=[d['RouteTableId']]), k)
        self.tag_resources([d['RouteTableId']], rt_tags)
        self.save()

    def create_subnet(self, affinity_group=0):
        subnet_tags = [
            { 'Key': 'affinity_group', 'Value':  str(affinity_group) }
        ]
        az = self.get_next_az(affinity_group)
        cidr = self.get_available_cidr_block()
        k, d = self.execute(ec2().create_subnet(
            AvailabilityZone=az,
            CidrBlock=cidr,
            VpcId=self.get_vpc_id()))
        k = 'Subnets'
        self.append_to_objs(k, d)
        self.waiter(ec2().describe_subnets(SubnetIds=[d['SubnetId']]), k)
        self.tag_resources([d['SubnetId']], subnet_tags)
        self.save()

    def associate_rt_subnet(self, affinity_group=0):
        rtb_id = self.get_af_rtb(affinity_group)
        for s in self.get_af_subnets(affinity_group):
            ec2().associate_route_table(
                RouteTableId=rtb_id,
                SubnetId=s)

    def create_internet_gateway(self, affinity_group=0):
        igw_tags = [
            {'Key': 'affinity_group', 'Value': str(affinity_group)}
        ]
        k, d = self.execute(ec2().create_internet_gateway())
        self[k] = d
        waiter(ec2().describe_internet_gateways(
            InternetGatewayIds=[d[k]['InternetGatewayId']]), k)
        ec2().attach_internet_gateway(
            InternetGatewayId=self['igw'],
            VpcId=self.get_vpc_id())
        rtb_id = self.get_af_rtb(affinity_group)
        subnet_ids = [s['SubnetId'] for s in \
            ec2().describe_subnets(SubnetIds=self['subnet'],
                Filters=[{'Name': 'tag:affinity_group', 'Values': [str(affinity_group)]}])\
                ['Subnets']]
        ec2().create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=self['igw'],
            RouteTableId=rtb_id)
        self.save()

    def create_ip_allocation(self):
        eipalloc_id = ec2().allocate_address(Domain='vpc')['AllocationId']
        self.append_to_objs('eipalloc', eipalloc_id)
        self.save()
        return eipalloc_id

    def create_nat_gateway(self, affinity_group=0):
        eipalloc_id = self.create_ip_allocation()
        subnet_id = self.get_af_subnets(affinity_group)[0]
        ngw_id = ec2().create_nat_gateway(
            AllocationId=eipalloc_id, SubnetId=subnet_id)['NatGateway']['NatGatewayId']
        self.save()
        print("Waiting for Nat Gateway to become available.")
        while ec2().describe_nat_gateways(NatGatewayIds=[ngw_id])\
            ['NatGateways'][0]['State'] != 'available': pass
        self.save()
        self.append_to_objs('ngw', ngw_id)
        self.tag_resources([subnet_id],[
            {'Key': 'ngw_id', 'Value': ngw_id},
            {'Key': 'ip_allocation_id', 'Value': eipalloc_id}])

    def delete_nat_gateways(self):
        try:
            for ngw_id in self['nat_gateways']:
                ec2().delete_nat_gateway(NatGatewayId=ngw_id)
            print("Waiting for NAT Gateways to delete.")
            while all(n != 'deleted' for n in [ngw['State'] for ngw in \
                ec2().describe_nat_gateways(NatGatewayIds=self['nat_gateways'])\
                ['NatGateways']]): pass
            del(self['ngw'])
            self.save()
        except KeyError:
            return 0

    def delete_ip_allocations(self):
        try:
            for eipalloc_id in self['eipalloc']:
                ec2().release_address(
                    AllocationId=eipalloc_id)
            del(self['eipalloc'])
            self.save()
        except KeyError:
            return 0

    def delete_route_tables(self):
        try:
            for rt in self['RouteTables']:
                for association in rt['Associations']:
                    ec2().disassociate_route_table(
                        AssociationId=association['RouteTableAssociationId'])
                ec2().delete_route_table(RouteTableId=rt['RouteTableId'])
            del(self['RouteTables'])
            self.save()
        except KeyError:
            return 0

    def delete_subnets(self):
        try:
            [ec2().delete_subnet(SubnetId=s['SubnetId']) for s in self['Subnets']]
            del(self['Subnets'])
            self.save()
        except KeyError:
            return 0

    def delete_internet_gateway(self):
        try:
            igw_id = self['igw']
            vpc_id = self['vpc']
            ec2().detach_internet_gateway(
                InternetGatewayId=igw_id,
                VpcId=vpc_id)
            ec2().delete_internet_gateway(
                InternetGatewayId=igw_id)
            del(self['igw'])
            self.save()
        except KeyError:
            return 0

    def delete_vpc(self):
        try:
            ec2().delete_vpc(
                VpcId=self['Vpc']['VpcId'])
            del(self['Vpc'])
            self.save()
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
