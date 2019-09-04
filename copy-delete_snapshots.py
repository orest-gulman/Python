import boto3
from datetime import date, datetime, timedelta

sns_arn = "arn:aws:sns:us-east-1:00000999999:AWS_LAMBDA_NOTIFICATIONS"

region_src = 'us-east-1'
region_dst = 'us-east-2'

client_src = boto3.client('ec2', region_name=region_src)
client_dst = boto3.client('ec2', region_name=region_dst)
ec2_resource = boto3.resource('ec2')

sns = boto3.client('sns', region_name=region_src)

retention_days = 3

date_today = datetime.today().strftime('%Y-%m-%d')
delete_on = datetime.today() + timedelta(retention_days)
delete_on = delete_on.strftime('%Y-%m-%d')


# Getting snapshots as per specified filter and only today created
def get_snapshots_src():
    response = client_src.describe_snapshots(
        Filters=[
            {'Name': 'owner-id', 'Values': ['00000999999']},
            {'Name': 'tag:Disaster_Recovery', 'Values': ['Full']}
        ]
    )
    snapshotsInDay = []
    for i in response["Snapshots"]:
        if i["StartTime"].strftime('%Y-%m-%d') == date.isoformat(date.today()):
        # if i["OwnerId"] == '00000999999' and i["StartTime"].strftime('%Y-%m-%d') == date.isoformat(date.today()):
            snapshotsInDay.append(i)
    return snapshotsInDay


# Filter snapshots by tag: 'delete_On' and value: today
def get_snapshots_dst():
    response = client_dst.describe_snapshots(
        Filters=[{'Name': 'tag:delete_On', 'Values': [date_today]}]
    )
    return response["Snapshots"]


# Creating a list of snapshot_id and respective tags in source region
def get_snapshot_list_src(snapshots_src):
    snapshot_list = []
    for snapshot in snapshots_src:
        snapshot_id = snapshot["SnapshotId"]
        snapshot_tags = snapshot["Tags"]
        snapshot_list.append((snapshot_id, snapshot_tags))
    return snapshot_list


# Creating a list of snapshot_id and respective tags in destination region
def get_snapshot_list_dst(snapshots_dst):
    snapshot_list = []
    for snapshot in snapshots_dst:
        snapshot_id = snapshot["SnapshotId"]
        tags = snapshot["Tags"]
        snapshot_list.append((snapshot_id, tags))
        # snapshot_list.append(snapshot_id)
    return snapshot_list


# Copying snapshot with tags
def copy_snapshot_src_to_dst(snapshot_id, snapshot_tags):
    try:
        copy_response = client_dst.copy_snapshot(
            Description='[Disaster Recovery] copied from us-east-1',
            SourceRegion=region_src,
            SourceSnapshotId=snapshot_id,
            DryRun=False,
            #           Encrypted=True,
            #           KmsKeyId='1e287363-89f6-4837-a619-00000999999',
        )
        new_snapshot_id = copy_response["SnapshotId"]
        snapshot_src_name = ([dic['Value'] for dic in snapshot_tags if dic['Key']=='Name'])
        message = ("Started copying.. snapshot_id: " + str(snapshot_id) + " for the instance: " + str(snapshot_src_name) + " from: " + str(region_src) + " to: " + str(region_dst) + " with new snapshot_id: " + str(new_snapshot_id) + ".\n")

        # Creating tags in snapshot in destination region
        tag_src = [new_snapshot_id]
        tag = client_dst.create_tags(
            DryRun=False,
            Resources=tag_src,
            Tags=snapshot_tags
        )
        return message

    except Exception as e:
        raise e


# Sending email notification via AWS SNS service
def send_sns(message):
        if message:
            print("Sending SNS alert")
            response = sns.publish(
                TargetArn=sns_arn,
                MessageStructure='string',
                Subject=("AWS LAMBDA FUNCTION NOTIFICATION"),
                Message=(message)
        )


def lambda_handler(event, context):
    snapshots_src = get_snapshots_src()
    snapshot_list_src = get_snapshot_list_src(snapshots_src)
    # print(*snapshot_list_src, sep="\n")
    message = ""
    c = 0
    for i in snapshot_list_src:
        if c < 5:
            snapshot_id = i[0]
            snapshot_tags = i[1]
            snapshot_tags_filtered = ([item for item in snapshot_tags if item['Key'] != 'aws:backup:source-resource'])
            snapshot_tags_filtered.append({'Key': 'delete_On', 'Value': delete_on})
            snapshot_tags_filtered.append({'Key': 'src_Id', 'Value': snapshot_id})
            message += copy_snapshot_src_to_dst(snapshot_id, snapshot_tags_filtered)
            c = c + 1

        else:
            response = sns.publish(
                TargetArn=sns_arn,
                MessageStructure='string',
                Subject=("AWS LAMBDA FUNCTION ALERT"),
                Message=("There are > then 5 snapshots need's to be copyied to destination region")
            )
            exit(0)


    snapshots_dst = get_snapshots_dst()
    snapshot_list_dst = get_snapshot_list_dst(snapshots_dst)
    # print(*snapshot_list_dst, sep="\n")
    if snapshot_list_dst:
        message += ("\n\n")
        # Deleting snapshots with tag: delete_On and value: "current day" in destination region
        for i in snapshot_list_dst:
            snapshot_id = i[0]
            snapshot_tags = i[1]
            snapshot_dst_name = ([dic['Value'] for dic in snapshot_tags if dic['Key']=='Name'])
            try:
                client_dst.delete_snapshot(SnapshotId=snapshot_id)
                message += ("Deleted snapshot_id: " + snapshot_id + " for the instance: " + str(snapshot_dst_name) + " in " + region_dst + " region" + ".\n")
            except Exception as e:
                raise e

    if message:
        send_sns(message)
        print(message)
    else:
        response = sns.publish(
                TargetArn=sns_arn,
                MessageStructure='string',
                Subject=("AWS LAMBDA FUNCTION ALERT"),
                Message=("Message wasn't generated by script")
        )

