docker stop mee6 && docker rm mee6
docker run --name mee6 -d --restart="always" --env-file envfile.list --link redis:redis mee6-bot
docker stop mee6-web && docker rm mee6-web
docker run -d --restart="always" --name mee6-web --link redis:redis --env-file envfile.list mee6-web
