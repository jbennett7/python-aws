from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

import yaml
from vpc import AwsVpc
PATH='./.aws_dump.yaml'

if __name__ == '__main__':
    vpc = AwsVpc(PATH)
    vpc.create_vpc()
    vpc.create_route_table()
#   vpc.create_subnet()
#   vpc.associate_rt_subnet()
#   vpc.create_subnet()
#   vpc.create_subnet()
#   vpc.create_subnet()
#   vpc.create_subnet()
#   vpc.create_internet_gateway()
    print(vpc['RouteTables']);print("\n")

    vpc.delete_route_tables()
#   vpc.delete_subnets()
#   vpc.delete_internet_gateway()
#   vpc.delete_vpc()
    print(vpc)
