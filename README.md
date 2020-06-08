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
AWS.create_public_subnets()
```
2. Pure private subnets,
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_private_subnets()
```
3. Public/Private with the public subnets set up as a demarc zone.
```python3.7
AWS = AWSEnvironment()
AWS.create_vpc()
AWS.create_private_subnets()
AWS.create_public_subnets()
AWS.create_nat_gateway(AWS.get_subnets('public')[0])
```

## Details
* The purpose of this is to setup an environment with the least amount of configuraiton
as possible. 
* Many resources are created under the hood and are not meant to be configurable.
* The identifiers for all resources created are kept in `self.objs` dictionary.
