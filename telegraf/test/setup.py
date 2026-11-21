from setuptools import setup, find_packages

version = '0.0.1.dev0'
name = 'slapos.test.telegraf'
with open("README.md") as f:
  long_description = f.read()

setup(
    name=name,
    version=version,
    description="Test for the Telegraf software release",
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    install_requires=[
        'slapos.core',
        'slapos.libnetworkcache',
        'requests',
        'psutil',
        # runs the OPC UA server used by the tests
        'asyncua',
    ],
    zip_safe=True,
)
