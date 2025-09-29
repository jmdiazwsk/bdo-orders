# Crear bucket S3
docker-compose exec localstack awslocal s3 mb s3://bdo-orders --region eu-west-1

# Crear tópico SNS
docker-compose exec localstack awslocal sns create-topic --name bdo-alerts --region eu-west-1

# Verificar recursos
docker-compose exec localstack awslocal s3 ls
docker-compose exec localstack awslocal sns list-topics