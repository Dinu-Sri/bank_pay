from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="bank_pay",
    version="2.0.0",
    description="Unified payment gateway for Frappe LMS - Bank Transfer & PayHere",
    author="SL Tax Solution",
    author_email="info@sltaxsolution.lk",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
