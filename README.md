# BUAA-Database-Project-backend

北航计算机学院 2023 秋季学期数据库作业项目后端

## 运行方式

先根据 config_example.yaml 编写配置文件 config.yaml

数据存储方面此项目使用了 MySQL 和 Minio，使用前需要先部署对应服务并在 config.yaml 中配置

### Windows

建立虚拟环境

```shell
python -m venv venv
```

激活虚拟环境

```shell
cd venv/Scripts
activate.bat
cd ../../
```

安装依赖

```shell
pip install -r requirements.txt
```

运行服务

```shell
python manage.py runserver
```

### Linux

建立虚拟环境

```shell
python3 -m venv venv
```

激活虚拟环境

```shell
source venv/bin/activate
```

安装依赖

```shell
pip3 install -r requirements.txt
```

运行服务

```shell
python3 manage.py runserver
```