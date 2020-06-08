from boto3 import resource, client
from ipaddress import ip_network
from time import sleep

class AWSEnvironment(object):

    def __init__(self):
        # The keys follow the resource id preface for aws resource ids.
        self.objs = {}

    def _append_to_objs(self, key, value):
        try:
            self.objs[key].append(value)
        except KeyError:
            self.objs[key] = []
            self.objs[key].append(value)

    def _tag_resources(self, resource_ids, tags):
        client('ec2').create_tags(
            Resources=resource_ids, Tags=tags)

    def create_vpc(self, cidr_block='10.0.0.0/16'):
        """
        Creates the VPC with a cidr block.
        """
        vpc_id = client('ec2').create_vpc(
            CidrBlock=cidr_block)['Vpc']['VpcId']
        while client('ec2').describe_vpcs(
            VpcIds=[vpc_id])['Vpcs'][0]['State'] != 'available':
                sleep(2)
        self.objs['vpc'] = vpc_id

    def create_subnets(self, stype='private', az_count=2):
        """
        Creates subnets inside mulitple availability zones
        with the following resources:

            * An internet gateway if `stype` == 'public'.
            * A route table to associate with the subnets.
            * A route created in the route table for internet traffic
              if `stype` == 'public'.
            * An `az_count` number of subnets in different availability zones.
            * Route table associations for each subnet to the route table.
        """
        vpc_id, cidr_block = self.get_vpc()
        subnet_tag = {'Key': 'type', 'Value': stype}

        # only one internet gateway per vpc and
        # only created if public subnets exist.
        if stype == 'public' and 'igw' not in self.objs:
            self.objs['igw'] = client('ec2').create_internet_gateway()\
                ['InternetGateway']['InternetGatewayId']
            client('ec2').attach_internet_gateway(
                InternetGatewayId=self.objs['igw'],
                VpcId=self.objs['vpc'])

        # only one route table per subnet type for the vpc.
        if 'rtb' not in self.objs or \
            [rtb for rtb in client('ec2').describe_route_tables(
            RouteTableIds=self.objs['rtb'])['RouteTables'] \
            for t in rtb['Tags'] if t['Key'] == 'type' \
            and t['Value'] == stype] == []:
                rtb_id = client('ec2').create_route_table(
                    VpcId=self.objs['vpc'])['RouteTable']['RouteTableId']
                self._tag_resources([rtb_id], [subnet_tag])
                self._append_to_objs('rtb', rtb_id)
                if stype == 'public':
                    client('ec2').create_route(
                        DestinationCidrBlock='0.0.0.0/0',
                        GatewayId=self.objs['igw'],
                        RouteTableId=rtb_id)
                    self._append_to_objs('route', 
                        {'rtb': rtb_id, 'destination_cidr': '0.0.0.0/0'})

        i=1 if stype == 'public' else 0
        cidr_partition = str(list(ip_network(cidr_block).subnets())[i])
        az_list = [az['ZoneName'] \
            for az in client('ec2').describe_availability_zones()\
            ['AvailabilityZones']][:az_count]
        for az in az_list:
            cidr_list = [s['CidrBlock'] for s in client('ec2').describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [self.objs['vpc']]}])['Subnets']]
            cidr = list(set([str(c) for c in \
                list(ip_network(cidr_partition).subnets(new_prefix=24))]) -
                set(cidr_list))
            cidr.sort()
            cidr = cidr[0]
            subnet_id = client('ec2').create_subnet(
                AvailabilityZone=az,
                CidrBlock=cidr,
                VpcId=self.objs['vpc'])['Subnet']['SubnetId']
            while client('ec2').describe_subnets(
                SubnetIds=[subnet_id])['Subnets'][0]['State'] != 'available':
                    sleep(2)
            self._tag_resources([subnet_id], [subnet_tag])
            self._append_to_objs('subnet', subnet_id)
            rtbassoc_id = client('ec2').associate_route_table(
                RouteTableId=rtb_id,
                SubnetId=subnet_id)['AssociationId']
            self._append_to_objs('rtbassoc', rtbassoc_id)

    def create_nat_gateway(self, subnet_id):
        """
        Creates a nat gateway for the public/private demarc subnetting strategy.
        """
        eipalloc_id = client('ec2').allocate_address(Domain='vpc')['AllocationId']
        self._append_to_objs('eipalloc', eipalloc_id)
        ngw_id = client('ec2').create_nat_gateway(
            AllocationId=eipalloc_id, SubnetId=subnet_id)['NatGateway']['NatGatewayId']
        print("Waiting for Nat Gateway to become available.")
        while client('ec2').describe_nat_gateways(NatGatewayIds=[ngw_id])\
            ['NatGateways'][0]['State'] != 'available':
                sleep(5)
        self._append_to_objs('nat_gateways', ngw_id)
        self._tag_resources([subnet_id],[
            {'Key': 'ngw_id', 'Value': ngw_id},
            {'Key': 'ip_allocation_id', 'Value': eipalloc_id}])
        rt = next(rt for rt in \
            client('ec2').describe_route_tables(RouteTableIds=self.objs['rtb'])\
            ['RouteTables'] for t in rt['Tags'] \
            if t['Key'] == 'type' and t['Value'] == 'private')

    def get_subnets(self, sub_type):
        try:
            return [s['SubnetId'] for s in \
                    client('ec2').describe_subnets(SubnetIds=self.objs['subnet'])['Subnets'] \
                    for t in s['Tags'] if t['Key'] == 'type' and t['Value'] == sub_type]
        except KeyError:
            return []

    def get_vpc(self):
        vpc = client('ec2').describe_vpcs(
            VpcIds=[self.objs['vpc']])['Vpcs'][0]
        return vpc['VpcId'], vpc['CidrBlock']

    def delete_nat_gateways(self):
        try:
            for ngw_id in self.objs['nat_gateways']:
                client('ec2').delete_nat_gateway(NatGatewayId=ngw_id)
            print("Waiting for NAT Gateways to delete.")
            while all(n != 'deleted' for n in [ngw['State'] for ngw in \
                client('ec2').describe_nat_gateways(NatGatewayIds=self.objs['nat_gateways'])\
                ['NatGateways']]):
                            sleep(5)
            del(self.objs['nat_gateways'])
        except KeyError:
            return 0

    def delete_ip_allocations(self):
        try:
            for eipalloc_id in self.objs['eipalloc']:
                client('ec2').release_address(
                    AllocationId=eipalloc_id)
            del(self.objs['eipalloc'])
        except KeyError:
            return 0

    def delete_routes(self):
        try:
            for route in self.objs['route']:
                rtb_id = route['rtb']
                dest_cidr = route['destination_cidr']
                client('ec2').delete_route(
                    DestinationCidrBlock=dest_cidr,
                    RouteTableId=rtb_id)
            del(self.objs['route'])
        except KeyError:
            return 0

    def delete_route_table_associations(self):
        try:
            for rtbassoc_id in self.objs['rtbassoc']:
                client('ec2').disassociate_route_table(
                    AssociationId=rtbassoc_id)
            del(self.objs['rtbassoc'])
        except KeyError:
            return 0

    def delete_route_tables(self):
        try:
            for rtb_id in self.objs['rtb']:
                client('ec2').delete_route_table(
                    RouteTableId=rtb_id)
            del(self.objs['rtb'])
        except KeyError:
            return 0

    def delete_subnets(self):
        try:
            for subnet_id in self.objs['subnet']:
                client('ec2').delete_subnet(SubnetId=subnet_id)
            del(self.objs['rtb'])
        except KeyError:
            return 0

    def delete_internet_gateway(self):
        try:
            igw_id = self.objs['igw']
            vpc_id = self.objs['vpc']
            client('ec2').detach_internet_gateway(
                InternetGatewayId=igw_id,
                VpcId=vpc_id)
            client('ec2').delete_internet_gateway(
                InternetGatewayId=igw_id)
        except KeyError:
            return 0

    def delete_vpc(self):
        try:
            client('ec2').delete_vpc(
                VpcId=self.objs['vpc'])
        except KeyError:
            return 0

    def delete_all(self):
        self.delete_nat_gateways()
        self.delete_ip_allocations()
        self.delete_routes()
        self.delete_route_table_associations()
        self.delete_route_tables()
        self.delete_subnets()
        self.delete_internet_gateway()
        self.delete_vpc()

if __name__ == '__main__':
  AWS = AWSEnvironment()
  AWS.create_vpc()
  AWS.create_subnets()
  AWS.create_subnets(stype='public')
  AWS.create_nat_gateway(AWS.get_subnets('public')[0])
  print(AWS.objs)
  AWS.delete_all()
