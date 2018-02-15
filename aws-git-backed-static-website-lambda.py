#!/usr/bin/python2.7
#
# Lambda function for git-backed-static-website
#
# For more info, see: TBD
#
# This Lambda function is invoked by CodePipeline.
# - Download a ZIP file from the CodePipeline artifact S3 bucket
# - Unzip the contents into a temporary directory
# - Sync the contents to the S3 bucket specified in the request
#
from __future__ import print_function
from boto3.session import Session
import boto3
import botocore
import os
import time
import zipfile
import tempfile
import shutil
import subprocess
import traceback

code_pipeline = boto3.client('codepipeline')
cloudfront = boto3.client('cloudfront')

def setup(event):
    # Extract attributes passed in by CodePipeline
    job_id = event['CodePipeline.job']['id']
    job_data = event['CodePipeline.job']['data']
    artifact = job_data['inputArtifacts'][0]
    config = job_data['actionConfiguration']['configuration']
    credentials = job_data['artifactCredentials']
    from_bucket = artifact['location']['s3Location']['bucketName']
    from_key = artifact['location']['s3Location']['objectKey']
    from_revision = artifact['revision']
    #output_artifact = job_data['outputArtifacts'][0]
    #to_bucket = output_artifact['location']['s3Location']['bucketName']
    #to_key = output_artifact['location']['s3Location']['objectKey']

    # Temporary credentials to access CodePipeline artifact in S3
    key_id = credentials['accessKeyId']
    key_secret = credentials['secretAccessKey']
    session_token = credentials['sessionToken']
    session = Session(aws_access_key_id=key_id,
                      aws_secret_access_key=key_secret,
                      aws_session_token=session_token)
    s3 = session.client('s3',
                        config=botocore.client.Config(signature_version='s3v4'))

    return (job_id, s3, from_bucket, from_key, from_revision)

def download_source(s3, from_bucket, from_key, from_revision, source_dir):
    with tempfile.NamedTemporaryFile() as tmp_file:
        #TBD: from_revision is not used here!
        s3.download_file(from_bucket, from_key, tmp_file.name)
        with zipfile.ZipFile(tmp_file.name, 'r') as zip:
            zip.extractall(source_dir)

def handler(event, context):
    try:
        (job_id, s3, from_bucket, from_key, from_revision) = setup(event)

        to_bucket = os.environ['site_bucket']
        cloudfront_distribution = os.environ['cloudfront_distribution']

        # Directories for source content, and transformed static site
        source_dir = tempfile.mkdtemp()

        # Download and unzip the source for the static site
        download_source(s3, from_bucket, from_key, from_revision, source_dir)

        # Generate static website from source
        upload_static_site(source_dir, to_bucket)

        # Invalidate content cached in the CloudFront distribution
        invalidate_cloudfront(cloudfront_distribution)

        # Tell CodePipeline we succeeded
        code_pipeline.put_job_success_result(jobId=job_id)

    except Exception as e:
        print(e)
        traceback.print_exc()
        # Tell CodePipeline we failed
        code_pipeline.put_job_failure_result(jobId=job_id, failureDetails={'message': e, 'type': 'JobFailed'})

    finally:
      shutil.rmtree(source_dir)

    return "complete"

def upload_static_site(source_dir, to_bucket):
    # Sync Git branch contents to S3 bucket
    command = ["./aws", "s3", "sync", "--acl", "public-read", "--delete",
               source_dir + "/", "s3://" + to_bucket + "/"]
    print(command)
    print(subprocess.check_output(command, stderr=subprocess.STDOUT))

def invalidate_cloudfront(cloudfront_distribution):
    response = cloudfront.create_invalidation(
        DistributionId=cloudfront_distribution,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(time.time())
        }
    )
