###
# Global
###

region = "ca-central-1"
# Enable the new ARN format to propagate tags to containers (see config/terraform/aws/README.md)
billing_tag_key   = "CostCentre"
billing_tag_value = "CovidPortal_Staging"
environment       = "staging"

###
# AWS Cloud Watch - cloudwatch.tf
###

cloudwatch_log_group_name        = "covidportal_staging"
cloudwatch_log_group_name_qrcode = "qrcode_staging"

###
# AWS ECS - ecs.tf
###

ecs_name              = "covid-portal_staging"
metric_provider       = "stdout"
tracer_provider       = "stdout"
django_env            = "production"
django_allowed_hosts  = ".cdssandbox.xyz"
ecs_covid_portal_name = "covid-portal_staging"
ecs_qrcode_name       = "qrcode_staging"
new_relic_app_name    = "Staging-Terraform-Covid-Portal"
dual_urls             = "False"


#Autoscaling ECS

portal_autoscale_enabled = true

###
# AWS VPC - networking.tf
###

vpc_cidr_block = "172.16.0.0/16"
vpc_name       = "covidportal"

###
# AWS RDS - rds.tf
###

rds_db_subnet_group_name = "staging-portal-db"

# RDS Cluster
rds_server_db_name = "covid_portal"
rds_server_name    = "staging-covidportal-db"
rds_server_db_user = "postgres"
# Value should come from a TF_VAR environment variable (e.g. set in a Github Secret)
# rds_server_db_password       = ""
rds_server_allocated_storage = "5"
rds_server_instance_class    = "db.t3.medium"

###
# AWS Route 53 - route53.tf
###
# Value should come from a TF_VAR environment variable (e.g. set in a Github Secret)
route53_zone_name = "tf.covid-hcportal.cdssandbox.xyz"

###
# Cloud Based Sensor S3 bucket name prefix
###
cbs_satellite_bucket_name_prefix = "cbs-satellite-"
