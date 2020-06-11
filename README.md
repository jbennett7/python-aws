# Python-aws

## Description
Builds out an aws VPC environment.

## Quick Start
Make sure to turn on saving in `vpc.py`:
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_subnets(stype='public')
AWS._save('vpc_saved.py')
```
```bash
python3.7 vpc.py
```
Note the `vpc id` and the `subnet id`. set the `VPC_ID` and `SUBNET_ID`
variables to these. Then execute
```python3.7
VPC_ID="xxxxxx"
SUBNET_ID="xxxxx"
```
```bash
python3.7 eks.py
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
eks.authorize_security_group_policies()
eks.revoke_security_group_policies()
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
