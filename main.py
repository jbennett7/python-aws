from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

import yaml
from vpc import Vpc
from eks import Eks
from obj import AwsObjectDict
from yaml.representer import Representer
PATH='./.aws_dump.yaml'

def test_vpc():
    aws_env = Vpc()
    aws_env.create_vpc()
    aws_env.create_subnets()
    aws_env.create_subnets(stype='public')
    print(aws_env.objs)
    aws_env._save(PATH)
    del(aws_env)
    second = Vpc(path=PATH)
    second.delete_all()
    try:
        remove(PATH)
    except FileNotFoundError as e:
        pass

def create_vpc():
    aws_env = Vpc()
    aws_env.create_vpc()
    aws_env.create_subnets()
    aws_env.create_subnets(stype='public')
    print(aws_env.objs)
    aws_env._save(PATH)

def load_vpc(path):
    return Vpc(path=path)

def foo():
    aws_env = Vpc(path=PATH)
    vpc_id = aws_env.objs['vpc']

    eks = Eks(vpc_id=vpc_id)
    eks.create_eks_cluster_role()
    eks.create_security_groups()
    eks.authorize_security_group_policies()

    print(eks.objs)
    eks.revoke_security_group_policies()
    eks.delete_security_groups()
    eks.delete_eks_cluster_role()

def delete_vpc(vpc):
    vpc.delete_all()
    try:
        remove(PATH)
    except FileNotFoundError as e:
        pass

def foo2():
    aws_env = Vpc(PATH)

    eks = Eks(PATH)
    eks.create_eks_cluster_role()
    eks.create_security_groups()
    eks.authorize_security_group_policies()

    eks.revoke_security_group_policies()
    eks.delete_security_groups()
    eks.delete_eks_cluster_role()
#   aws_env.delete_all()
    print(eks.objs)

def foo3():
    aws_env = Vpc()
    aws_env.create_vpc()
    aws_env.create_subnets()
    aws_env.create_subnets(stype='public')
    print(aws_env.objs)
    aws_env._save(PATH)
#   aws_env.delete_all()
#   print(aws_env.objs)

if __name__ == '__main__':
    aws_env = AwsObjectDict(PATH)
    vpc = Vpc(aws_env)
    vpc.create_vpc()
    vpc.create_subnets()
#   vpc.create_subnets(stype='public')
#   print(vpc.get_subnets('public'))
#   aws_env.save()
    print(aws_env)
    vpc.delete_route_tables()
    print(aws_env)
    vpc.delete_subnets()
    print(aws_env)
    vpc.delete_vpc()
    print(aws_env)
    aws_env.save()

#   vpc.delete_all()

#   aws_env.save()
#   aws_env.load()
#   print(aws_env)
