Cloud Integration
=================

```{contents}
---
depth: 1
local: true
backlinks: none
---
```

## Amazon Web Services ##

Amazon Web Services (AWS) offers [EC2 instances with NVIDIA GPU support](https://aws.amazon.com/ec2/instance-types/#Accelerated_Computing). NVTabular can be used with 1x, 4x, or 8x GPU instances or multiple nodes. We're using an EC2 instance with 8x NVIDIA A100 GPUs to demonstrate the steps below. Check out the $/h for this instance type and adjust the type.

To run NVTabular on the cloud using AWS, do the following:

1. Start the AWS EC2 instance with the [NVIDIA Deep Learning AMI image](https://aws.amazon.com/marketplace/pp/NVIDIA-NVIDIA-Deep-Learning-AMI/B076K31M1S) using the aws-cli.
   ```
   # Starts the P4D instance with 8x NVIDIA A100 GPUs (take a look at the $/h for this instance type before using them)
   aws ec2 run-instances --image-id ami-04c0416d6bd8e4b1f --count 1 --instance-type p4d.24xlarge --key-name <MyKeyPair> --security-groups <my-sg>
   ```

2. SSH into the machine.

3. Create a RAID volume by running the following command:

   Depending on the EC2 instance, the machine may include local disk storage. We can optimize the performance by creating a
   [RAID volume](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/raid-config.html). Based on our experience, two NVMe volumes yield the best performance.

   ```
   sudo mdadm --create --verbose /dev/md0 --level=0 --name=MY_RAID --raid-devices=2 /dev/nvme1n1 /dev/nvme2n1

   sudo mkfs.ext4 -L MY_RAID /dev/md0
   sudo mkdir -p /mnt/raid
   sudo mount LABEL=MY_RAID /mnt/raid

   sudo chmod -R 777 /mnt/raid

   # Copy dataset inside raid directory:
   cp -r data/ /mnt/raid/data/
   ```

4. Launch the NVTabular Docker container by running the following command:
   ```
   docker run --gpus all --rm -it -p 8888:8888 -p 8797:8787 -p 8796:8786 --ipc=host --cap-add SYS_PTRACE -v /mnt/raid:/raid nvcr.io/nvidia/nvtabular:0.3 /bin/bash
   ```

5. Start the jupyter-lab server by running the following command:
   ```
   jupyter-lab --allow-root --ip='0.0.0.0' --NotebookApp.token='<password>'
   ```

## Google Cloud Platform ##

The Google Cloud Platform (GCP) offers [Compute Engine instances with NVIDIA GPU support](https://cloud.google.com/compute/docs/gpus). We're using a VM with 8x NVIDIA A100 GPUs and eight local SSD-NVMe devices configured as RAID 0 to demonstrate the steps below.

To run NVTabular on the cloud using GCP, do the following:

1. Configure and create the VM as follows:
    * **GPU**: 8xA100 (a2-highgpu-8g)
    * **Boot Disk**: Ubuntu version 18.04
    * **Storage**: Local 8xSSD-NVMe

2. Install the NVIDIA drivers and CUDA by running the following commands:

   ```shell
   curl -O https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/cuda-ubuntu1804.pin
   sudo mv cuda-ubuntu1804.pin /etc/apt/preferences.d/cuda-repository-pin-600
   sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/7fa2af80.pub
   sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/ /"
   sudo apt -y update
   sudo apt -y install cuda
   nvidia-smi # Check installation
   ```

   > For more information, refer to [Install GPU drivers](https://cloud.google.com/compute/docs/gpus/install-drivers-gpu)
   > in the Google Cloud documentation.

3. [Install Docker](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) by running the following commands:

   ```shell
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -s -L https://nvidia-merlin.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
      && curl -s -L https://nvidia-merlin.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get -y update
   sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   sudo docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi # Check Installation
   ```

4. Configure the storage as RAID 0 by running the following commands:

   ```shell
   sudo mdadm --create --verbose /dev/md0 --level=0 --name=MY_RAID --raid-devices=2 /dev/nvme0n1 /dev/nvme0n2
   sudo mkfs.ext4 -L MY_RAID /dev/md0
   sudo mkdir -p /mnt/raid
   sudo mount LABEL=MY_RAID /mnt/raid
   sudo chmod -R 777 /mnt/raid

   # Copy data to RAID
   cp -r data/ /mnt/raid/data/
   ```

5. Run the container by running the following command:

   ```shell
   docker run --gpus all --rm -it -p 8888:8888 -p 8797:8787 -p 8796:8786 --ipc=host --cap-add SYS_PTRACE -v /mnt/raid:/raid nvcr.io/nvidia/nvtabular:0.3 /bin/bash
   ```

## Databricks ##

Databricks has developed a web-based platform on top of Apache Spark to provide automated cluster management. Databricks currently supports [custom containers](https://docs.databricks.com/clusters/custom-containers.html)

To run NVTabular on Databricks, do the following:

1. Create a custom NVTabular container using Databricks runtime.

   **NOTE**: If any of the default dependencies that come with the Databricks cluster are changed to a different version, the Databricks cluster won't be able to detect the Spark
   driver. As a workaround, the NVIDIA RAPIDS team has created a
   [Docker container](https://github.com/rapidsai/cloud-ml-examples/tree/main/databricks/docker) so that RAPIDS can run inside a Databricks cluster.

2. Extend the container and add NVTabular and PyTorch so that they can run inside Databricks.

3. Select the appropriate version of the NVTabular Conda repo.

   **NOTE**: All versions of the NVTabular conda repo are listed [here](https://anaconda.org/nvidia/nvtabular/files?version=).

4. Clone the cloud-ml-example repo by running the following command:
   ```
   git clone https://github.com/rapidsai/cloud-ml-examples.git
   ```

5. Add the selected version of the NVTabular Conda repo to the [rapids-spec.txt](https://github.com/rapidsai/cloud-ml-examples/blob/main/databricks/docker/rapids-spec.txt) file by
   running the following command:
   ```
   cd databricks
   echo "https://conda.anaconda.org/nvidia/linux-64/nvtabular-0.6.1-py38_0.tar.bz2" >> docker/rapids-spec.txt
   ```

6. To install PyTorch, add the fastai pip package install to the Dockerfile by running the following command:
   ```
   RUN pip install fastai
   ```

7. Build the container and push it to Docker Hub or the AWS Elastic Container Registry by running the following command:
   ```
   docker build --tag <repo_name>/databricks_nvtabular:latest docker push <repo_name>/databricks_nvtabular:latest
   ```

8. Use the custom container to spin up the Databricks cluster.

   ![Databricks NVTabular](/images/nvt_databricks.png)

9. Select a GPU node for the Worker and Driver.
   Once the Databricks cluster is up, NVTabular will be running inside of it.

## AWS SageMaker ##

[AWS SageMaker](https://aws.amazon.com/sagemaker/) is a service from AWS to "build, train and deploy machine learning" models. It automates and manages the MLOps workflow. It supports jupyter notebook instances enabling users to work directly in jupyter notebook/jupyter lab without any additional configurations. In this section, we will explain how to run NVIDIA Merlin (NVTabular) on AWS SageMaker notebook instances. We adopted the work from [Eugene](https://twitter.com/eugeneyan/) from his [twitter post](https://twitter.com/eugeneyan/status/1470916049604268035). We tested the workflow on February, 1st, 2022, but it is not integrated into our CI workflows. Future release of Merlin or Merlin's dependencies can cause issues.

To run the [movielens example](https://github.com/NVIDIA-Merlin/NVTabular/tree/main/examples/getting-started-movielens) on AWS SageMaker, do the following:

1. Login into your AWS console and select AWS SageMaker.

2. Select `Notebook` -> `Notebook instances` -> `Create notebook instance`. Give the instance a name and select a notebook instance type with GPUs. For example, we selected `ml.p3.2xlarge`. Please review the associated costs with each instance type. As a platform identifier, select `notebook-al2-v1`. The previous platform identifier runs with TensorFlow 2.1.x and we had more issue to update it to TensorFlow 2.6.x. The `volume size` can be increased in the section `Additional configuration`.

3. After the instance is running, connect to jupyter lab.

4. Start a terminal to have access to the command line.

5. The image contains many conda environments, which requires ~60GB of disk space. You can remove some of them to free disk space in the folder `/home/ec2-user/anaconda3/envs/`

6. Clone the NVTabular repository and install the conda environment.

```
cd /home/ec2-user/SageMaker/
git clone https://github.com/NVIDIA-Merlin/NVTabular.git
conda env create -f=NVTabular/conda/environments/nvtabular_aws_sagemaker.yml
```

7. Activate the conda environment

```
source /home/ec2-user/anaconda3/etc/profile.d/conda.sh
conda activate nvtabular
```

8. Install additional packages, such as TensorFlow or PyTorch

```
pip install tensorflow-gpu
pip install torch
pip install graphviz
```

9. Install Transformer4Rec, torchmetrics and ipykernel

```
conda install -y -c nvidia -c rapidsai -c numba -c conda-forge transformers4rec
conda install -y torchmetrics ipykernel
```

10. Add conda environment as ipykernel

```
python -m ipykernel install --user --name=nvtabular
```

11. You can switch in jupyter lab and run the [movielens example](https://github.com/NVIDIA-Merlin/NVTabular/tree/main/examples/getting-started-movielens).

This workflow enables NVTabular ETL and training with TensorFlow or Pytorch. Deployment with Triton Inference Server will follow soon.
