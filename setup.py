from setuptools import setup

setup(
    name="cocotb-xsi",
    packages=["cocotb_xsi", "cocotb_xsi.stub"],
    package_dir={"": "src"},
    author="Tomasz Hemperek",
    author_email="themperek@gmail.com",
    description="Limited cocotb/Python interface for Xilinx XSIM simulator",
    long_description="""
    Enables running cocotb/Python unit tests with Xilinx XSIM simulator
    """,
    license="Apache 2.0",
    keywords=["SystemVerilog", "Verilog", "RTL", "cocotb", "Python"],
    url="https://github.com/themperek/cocotb-xsim",
    setup_requires=["setuptools_scm"],
    install_requires=["cocotb>=1.7,<=1.8"],
    version="0.0.1",
)
