# Python-aws

## Description
Builds out an aws VPC environment.

## Quick Start
```bash
python3.7 env.py
```

## Deployment Strategies
This can deploy three types of environments:
1. Pure public subnets,
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_subnets(stype='public')
```
2. Pure private subnets,
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_subnets()
```
3. Public/Private with the public subnets set up as a demarc zone.
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_subnets()
AWS.create_subnets(stype='public')
AWS.create_nat_gateway(AWS.get_subnets('public')[0])
```

## New Features
* __10-JUN-2020__: Adds a method to save and load the current state:
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.save('./vpc_saved.yaml')
del(AWS)
AWS2 = AWSEnvironment(path='./vpc_saved.yaml')
AWS2.create_subnets()
print(AWS2.objs)
```
* __10-JUN-2020__: Preliminary code for setting up an EKS cluster.
Right now it just creates the IAM role EKSRole, and four security groups:
```python3.7
eks = AWSEks(vpc_id=VPC_ID)
eks.create_eks_role()
eks.create_security_groups()
eks.authorize_control_plane_security_group_ingress()
eks.authorize_control_plane_security_group_egress()
eks.authorize_worker_node_security_group_ingress()
eks.revoke_worker_node_security_group_ingress()
eks.authorize_alb_security_group_ingress()
eks.revoke_alb_security_group_ingress()
eks.authorize_bastion_host_security_group_ingress()
eks.revoke_bastion_host_security_group_ingress()
eks.revoke_control_plane_security_group_ingress()
eks.revoke_control_plane_security_group_egress()
print(eks.objs)
eks.delete_security_groups()
eks.delete_eks_role()
print(eks.objs)
```

## Details
* The purpose of this module is to setup an AWS networking environment with
the least amount of configuraiton as possible. 
* Many resources are created under the hood and are not meant to be configurable.
* The identifiers for all resources created are kept in `self.objs` dictionary.
