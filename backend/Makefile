.DEFAULT_GOAL := help
help: ### Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

dev: ### Start the django dev server
	python manage.py runserver 0.0.0.0:8000

test: ### Run tests
ifdef t
	python manage.py test -k $(t)
else
	python manage.py test --parallel
endif

migration: ### create migrations
	python manage.py makemigrations

migrate: ### Run migrations
	python manage.py migrate

openapi: ### Generate the OpenApi spec schema at schema.yml
	 python manage.py spectacular --color --file ../openapi/schema.yml