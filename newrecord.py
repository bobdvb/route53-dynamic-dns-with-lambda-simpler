import time
import boto3
route53 = boto3.client('route53')
awslambda = boto3.client('lambda')
cloudformation = boto3.client('cloudformation')

newhz = False

# Check cloudformation stack has been deployed
try:
    stack = cloudformation.describe_stacks(StackName='DyndnsStack')
    if not (stack['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE' or stack['Stacks'][0]['StackStatus'] == 'UPDATE_COMPLETE'):
        print('Stack is being deployed try again in few minutes')
        exit()
except:
    print("Dyndns stack not found, ensure the right AWS CLI profile is being used.")
    exit()


# Get Lambda Function name
resources = cloudformation.list_stack_resources(StackName='DyndnsStack')
lambdafn = None
for resource in resources['StackResourceSummaries']:
    if resource['ResourceType'] == 'AWS::Lambda::Function':
        lambdafn = resource['PhysicalResourceId']
        break

if not lambdafn:
    print("Lambda function not found in stack.")
    exit()

lambdaurl = awslambda.get_function_url_config(
    FunctionName=lambdafn)['FunctionUrl']

print('Hosted zone name, i.e. example.com.')
hzname = ""
while not hzname:
    hzname = input()
    if not hzname:
        print('####################################################')
        print('#                                                  #')
        print('# Hosted zone name is required and cannot be empty #')
        print('#                                                  #')
        print('####################################################\n')
        print('Hosted zone name, i.e. example.com.')
print('Hostname (www.'+hzname+')')
hostname = input() or "www."+hzname
print('Record set TTL (60)')
ttl = input() or 60

hz = route53.list_hosted_zones_by_name(
    MaxItems='1',
    DNSName=hzname
)
try:
    hzid = hz['HostedZones'][0]['Id'].split('/')[2]
    if hz['HostedZones'][0]['Name'] != hzname+'.':
        print(hz['HostedZones'][0]['Name'])
        raise Exception('Found hosted zone is not matching '+hzname)
except:
    print("Hosted zone " + hzname + " not found.")
    print("Do you want to create it? (y/n)")
    create=input()
    if create == 'y':
        try:
            route53.create_hosted_zone(
                Name= hzname,
                CallerReference= str(time.time())
            )
            hz=route53.list_hosted_zones_by_name(
                MaxItems= '1',
                DNSName= hzname
            )
            hzid=hz['HostedZones'][0]['Id'].split('/')[2]
            newhz=True
        except:
            print("Could not create hosted zone. Ensure '" +
                  hzname+"' is a valid domain name.")
            exit()
    else:
        print("You need an hosted zone to continue.")
        exit()

secret=""
while not secret:
    print('Enter the secret for the new record set.')
    secret=input()
    print('Confirm the secret: ')
    secret2=input()
    if secret != secret2:
        secret=""
        print('#####################################')
        print('#                                   #')
        print('# Secret does not match. Try again. #')
        print('#                                   #')
        print('#####################################')
        secret=""
        continue
print('##############################################')
print('#                                            #')
print('# The following configuration will be saved: #')
print('#                                            #')
print('  Host name:  '+hostname)
print('  Hosted zone id: '+hzid)
print('  Record set TTL: '+str(ttl))
print('  Secret: '+secret)
print('#                                            #')
print('#      do you want to continue? (y/n)        #')
print('#                                            #')
print('##############################################')
confirm=input()
if confirm == 'y':
    # Update Lambda environment variables
    print('\nUpdating Lambda environment variables...')
    try:
        # Get current environment variables
        lambda_config = awslambda.get_function_configuration(FunctionName=lambdafn)
        current_env = lambda_config.get('Environment', {}).get('Variables', {})

        # Update with new configuration
        current_env['ROUTE53_ZONE_ID'] = hzid
        current_env['ROUTE53_RECORD_TTL'] = str(ttl)
        current_env['SHARED_SECRET'] = secret

        # Update the Lambda function
        awslambda.update_function_configuration(
            FunctionName=lambdafn,
            Environment={'Variables': current_env}
        )

        print('Configuration saved.\n')
        print('#####################################################')
        print('#                                                   #')
        print('# The Serverless Dynamic DNS solution is now ready. #')
        print('#                                                   #')
        print('#####################################################')
        print('\nConfiguration details:')
        print('  Hosted zone ID: ' + hzid)
        print('  Record TTL: ' + str(ttl))
        print('  Validation mode: ' + current_env.get('VALIDATION_MODE', 'wildcard'))
        if current_env.get('VALIDATION_MODE', 'wildcard') == 'wildcard':
            print('  Allowed pattern: ' + current_env.get('ALLOWED_PATTERN', ''))
        else:
            print('  Allowed domains: ' + current_env.get('ALLOWED_DOMAINS', ''))
        print(
            '\n'+hostname+' can be updated with the following command:')
        print("./dyndns.sh -m set -u "+lambdaurl +
              " -h "+hostname+" -s "+secret)
        print('\n##########################################################################################\n')
    except Exception as e:
        print("Could not save configuration: " + str(e))
        exit()
else:
    print('Aborting.')
    if newhz:
        print('Do you want to delete the newly created hosted zone? (y/n)')
        delete = input()
        if delete == 'y':
            print('Deleting hosted zone...')
            route53.delete_hosted_zone(
                Id=hzid
            )
        else:
            print('Hosted zone '+hzname+'  not deleted.')
    exit()
