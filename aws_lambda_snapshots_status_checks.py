import boto3

sns_arn = "arn:aws:sns:us-east-1:000000999999:AWS_LAMBDA_NOTIFICATIONS"

region_src = 'us-east-1'
region_dst = 'us-east-2'
client_dst = boto3.client('ec2', region_name=region_dst)
ec2_resource = boto3.resource('ec2')


sns = boto3.client('sns', region_name=region_src)

def get_snapshots_dst():
    response = client_dst.describe_snapshots(
       Filters=[
           {'Name': 'owner-id', 'Values': ['000000999999']},
           {'Name': 'tag:Disaster_Recovery', 'Values': ['Full']}
       ]
    )
    errors = []
    for i in response["Snapshots"]:
            if not i["Progress"] == '100%' or not i["State"] == 'completed':
                errors.append(i)
    return errors


def get_snapshot_list_dst(snapshots_dst):
    snapshot_list = []
    for snapshot in snapshots_dst:
        snapshot_id = snapshot["SnapshotId"]
        tags = snapshot["Tags"]
        snapshot_list.append((snapshot_id, tags))
    return snapshot_list

def lambda_handler(event, context):
    snapshots_dst = get_snapshots_dst()
    snapshot_list_dst = get_snapshot_list_dst(snapshots_dst)
    message = ""
    # print(*snapshot_list_dst, sep="\n")
    if snapshot_list_dst:
        for i in snapshot_list_dst:
            snapshot_id = i[0]
            snapshot_tags = i[1]
            snapshot_dst_name = ([dic['Value'] for dic in snapshot_tags if dic['Key']=='Name'])
            try:
                message += ("Snapshots copied with an error: " + snapshot_id + " for the instance: " + str(snapshot_dst_name) + " in " + region_dst + " region" + ".\n")
            except Exception as e:
                raise e

        response = sns.publish(
            TargetArn=sns_arn,
            MessageStructure='string',
            Subject=("AWS LAMBDA FUNCTION ALERT"),
            Message=(message)
        )
    else:
        response = "All snapshots copied successful"
        return response
