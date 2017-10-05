python templates/nat.py > templates/nat.template
aws s3 sync . s3://gong-cf-templates
echo https://gong-cf-templates.s3.amazonaws.com/templates/nat.template

aws s3 sync . s3://gong-cf-templates-magic --profile=magic
echo https://gong-cf-templates-magic.s3.amazonaws.com/templates/nat.template
