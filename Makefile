.PHONY: tests coverage

tests:
	nosetests tests

coverage:
	nosetests --with-coverage --cover-branches --cover-package=coinbase tests
	coverage html --include='coinbase*'

release:
	python setup.py sdist bdist_wheel upload
