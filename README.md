# Python Fear and Greed API

A Python Flask API which returns data from Fear and Greed scraper

![cicd cloud run workflow](https://github.com/MatthewCYLau/python-fear-greed-api/actions/workflows/cicd-cloud-run.yaml/badge.svg)

API URL here: [`https://python-fear-greed-api-3i2mtbjusq-ew.a.run.app/`](https://python-fear-greed-api-3i2mtbjusq-ew.a.run.app/)

The list of repositories are as follow:

- Python Flask API repository [here](https://github.com/MatthewCYLau/python-fear-greed-api)
- Scraper and GCP infrastructure repository [here](https://github.com/MatthewCYLau/python-fear-greed-scraper)

## Run/build app locally

- Run app on host machine:

```bash
virtualenv -p /usr/bin/python3 venv
source venv/bin/activate
pip3 install -r requirements.txt 
python3 manage.py 
deactivate 
```

- Run app as container:

```bash
docker compose up --build
```

### Install new packages

```bash
pip3 install boto 
pip3 freeze > requirements.txt
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

[MIT](https://choosealicense.com/licenses/mit/)