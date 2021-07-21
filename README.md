
# Git-backed static website powered entirely by AWS

![diagram](https://raw.githubusercontent.com/alestic/aws-git-backed-static-website/master/aws-git-backed-static-website-architecture.gif "Architecture dagram: Git-backed static website powerd by AWS")

[![Launch CloudFormation stack][launchimg]][launch]

[launchimg]: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png

[launch]: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?templateURL=https:%2F%2Fs3.amazonaws.com%2Frun.alestic.com%2Fcloudformation%2Faws-git-backed-static-website-cloudformation.yml&stackName=aws-git-backed-static-website

## Blog Article

Please read the following blog article for more information:

[AWS Git-backed Static Website][blog]

[blog]: https://alestic.com/2016/10/aws-git-backed-static-website/

## Overview

This project contains a YAML CloudFormation template that, by default,
creates a CodeCommit Git repository and a static https website, along
with the necessary AWS infrastructure glue so that every change to
content in the Git repository is automatically deployed to the static
web site.

The website can serve the exact contents of the Git repository, or a
static site generator plugin (e.g., Hugo) can be specified on launch
to automatically generate the site content from the source in the Git
repository.

The required stack parameters are a domain name and an email address.

The primary output values are a list of nameservers to set in your
domain's registrar and a Git repository URL for adding and updating
the website content.

CodeCommit Git repository event notifications are sent to an SNS topic
and your provided email address is initially subscribed.

Access logs for the website are stored in an S3 bucket.

Benefits of this architecture include:

 - Trivial to launch - Can use aws-cli or AWS console (click "launch"
   above)

 - Maintenance-free - Amazon is responsible for managing all the
   services used.

 - Negligible cost at substantial traffic volume - Starts off as low
   as $0.51 per month if running alone in a new AWS account. (Route 53
   has no free tier.) Your cost may vary over time and if other
   resources are running in your AWS account.

 - Scales forever - No action is needed to support more web site
   traffic, though the costs for network traffic and DNS lookups will
   start to add up to more than a penny per month.

## Create CloudFormation stack for static website

This CloudFormation stack has an AWS Lambda plugin architecture that
supports arbitrary static site generators. Here are some generator
plugins that are currently available

1. [Identity transformation plugin][identity] - This copies the entire Git
   repository content to the static website with no
   modifications. This is currently the default plugin for the static
   website CloudFormation template.

2. [Subdirectory plugin][subdirectory] - This plugin is useful if your
   Git repository has files that should not be included as part of the
   static site. It publishes a specified subdirectory (e.g., "htdocs"
   or "public-html") as the static website, keeping the rest of your
   repository private.

3. [Hugo plugin][hugoplugin] - This plugin runs the popular
   [Hugo][hugo] static site generator. The Git repository should
   include all source templates, content, theme, and config.

You are welcome to make your own static site generators based on one
of these and pass it into the CloudFormation stack.

[identity]: https://github.com/alestic/aws-lambda-codepipeline-site-generator-identity
[subdirectory]: https://github.com/alestic/aws-lambda-codepipeline-site-generator-subdirectory
[hugoplugin]: https://github.com/alestic/aws-lambda-codepipeline-site-generator-hugo
[hugo]: https://gohugo.io/

## Create CloudFormation stack for static website

Here is the basic approach to creating the stack with CloudFormation.

    domain=example.com
    email=yourrealemail@anotherdomain.com

    template=aws-git-backed-static-website-cloudformation.yml
    stackname=${domain/./-}-$(date +%Y%m%d-%H%M%S)
    region=us-east-1

    aws cloudformation create-stack \
      --region "$region" \
      --stack-name "$stackname" \
      --capabilities CAPABILITY_IAM \
      --template-body "file://$template" \
      --tags "Key=Name,Value=$stackname" \
      --parameters \
        "ParameterKey=DomainName,ParameterValue=$domain" \
        "ParameterKey=NotificationEmail,ParameterValue=$email"
    echo region=$region stackname=$stackname

The above defaults to the Identity transformation plugin. You can
specify the Hugo static site generator plugin by adding these
parameters:

        "ParameterKey=GeneratorLambdaFunctionS3Bucket,ParameterValue=run.alestic.com" \
        "ParameterKey=GeneratorLambdaFunctionS3Key,ParameterValue=lambda/aws-lambda-site-generator-hugo.zip"

Go to the email address you used above and approve the SNS topic
subscription.

When the stack starts up, the ACM certificate will be in "pending"
status until you verify ownership of the domain.

If you are using "EMAIL" as the CertificateValidationMethod, then you
need to open the email sent to the address associated with your
domain's registration and approve it.

If you are using "DNS" as the CertificateValidationMethod, then go to
the AWS Certificate Manager (ACM) console, find the two pending
certificates, and click "Create record in Route 53" for both.

Once the ACM certificates are verified, the CloudFront distributions
will be created. This can take 20-40+ minutes to complete.

### Get the name servers for updating in the registrar

    hosted_zone_id=$(aws cloudformation describe-stacks \
      --region "$region" \
      --stack-name "$stackname" \
      --output text \
      --query 'Stacks[*].Outputs[?OutputKey==`HostedZoneId`].[OutputValue]')
    echo hosted_zone_id=$hosted_zone_id

    aws route53 get-hosted-zone \
      --id "$hosted_zone_id"    \
      --output text             \
      --query 'DelegationSet.NameServers'

Set nameservers in your domain registrar to the above.

### Get the Git clone URL

    git_clone_url_http=$(aws cloudformation describe-stacks \
      --region "$region" \
      --stack-name "$stackname" \
      --output text \
      --query 'Stacks[*].Outputs[?OutputKey==`GitCloneUrlHttp`].[OutputValue]')
    echo git_clone_url_http=$git_clone_url_http

### Use Git

    repository=$domain
    profile=$AWS_PROFILE   # The correct aws-cli profile name

    git clone \
      --config 'credential.helper=!aws codecommit --profile '$profile' --region '$region' credential-helper $@' \
      --config 'credential.UseHttpPath=true' \
      $git_clone_url_http

    cd $repository

## Using GitHub

Thanks to the folks at [Elementryx][elementryx], this CloudFormation
template has been extended to support public and private repositories
in GitHub as an alternative to AWS CodeCommit.

Your GitHub repository must already exist when you create or update
the CloudFormation stack. You must also generate a (secret) personal
access token on GitHub and save it in AWS SSM Parameter Store.

Here are Amazon's instructions for generating the GitHub personal
access token on GitHub (ignore the steps after you generate the token
on GitHub and copy it):

> https://docs.aws.amazon.com/quickstart/latest/cicd-taskcat/step2.html

Once you have the token, save it in SSM Parameter Store:

    github_token="YOUR-SECRET-GITHUB-TOKEN"
    github_token_key="/YOUR-SSM-PARAMETER-STORE-KEY-FOR-GITHUB-TOKEN"

    # Should be SecureString, but not yet supported by CloudFormation!
    aws ssm put-parameter \
      --type String \
      --name "$github_token_key" \
      --value "$gitub_token"

    unset github_token

Now set up these environment variables:

    source_type=GitHub
    github_user="YOUR-GITHUB-USER"
    github_repository="YOUR-GITHUB-REPO"
    github_token_key="SAME-AS-ABOVE"

and pass in these parameters when creating or updating the
CloudFormation stack above:

        "ParameterKey=SourceType,ParameterValue=$source_type" \
        "ParameterKey=GitHubRepository,ParameterValue=$github_repository" \
        "ParameterKey=GitHubUser,ParameterValue=$github_user" \
        "ParameterKey=GitHubToken,ParameterValue=$github_token_key"

[elementryx]: https://github.com/elementryx/codepipeline-powered-static-website

## Clean up after testing

### Delete a stack (mostly)

    aws cloudformation delete-stack \
      --region "$region" \
      --stack-name "$stackname"

This leaves behind:

  - Route 53 hosted zone
  - S3 buckets
  - Git repository

### Clean up Route 53 hosted zone

    domain=...

    hosted_zone_id=$(
      aws route53 list-hosted-zones \
        --output text \
        --query 'HostedZones[?Name==`'$domain'.`].Id'
    )
    echo hosted_zone_id=$hosted_zone_id
    aws route53 delete-hosted-zone \
      --id "$hosted_zone_id"

### Clean up S3 buckets

    # WARNING! DESTROYS CONTENT AND LOGS!

    aws s3 rm --recursive s3://logs.$domain
    aws s3 rb s3://logs.$domain
    aws s3 rm --recursive s3://$domain
    aws s3 rb s3://$domain
    aws s3 rb s3://www.$domain
    aws s3 rm --recursive s3://codepipeline.$domain
    aws s3 rb s3://codepipeline.$domain

That last command will fail, so go use the web console to delete the
versioned codepipeline bucket.

### Delete CodeCommit Git repository

    # WARNING! DESTROYS CONTENT!

    #aws codecommit delete-repository \
      --region "$region" \
      --repository-name "$domain"
