from setuptools import setup, find_packages

setup(
    name='easywebassets',
    version='0.1',
    url='http://github.com/frascoweb/easywebassets',
    license='MIT',
    author='Maxime Bouroumeau-Fuseau',
    author_email='maxime.bouroumeau@gmail.com',
    description='An easier way to use webassets',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=[
        'webassets'
    ]
)