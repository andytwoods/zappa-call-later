from setuptools import setup

setup(
    name='zappa-call-later',
    version='1.0.2',
    packages=['zappa-call-later'],
    url='https://github.com/andytwoods/zappa-call-later',
    license='MIT License',
    author='andytwoods',
    author_email='andytwoods@gmail.com',
    description='store future tasks in the db and call them after set delays',
	install_requires=['django-picklefield']
)
