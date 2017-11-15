FROM continuumio/miniconda:4.3.11

RUN mkdir /helper
COPY ./environment.yml /helper
RUN conda env create -f /helper/environment.yml
RUN apt-get -y install libgl1-mesa-glx
RUN apt-get install libgomp1

RUN mkdir /scripts
COPY ./calc_image_translations.py /scripts
COPY ./image_registration.py /scripts
RUN touch /scripts/__init__.py
