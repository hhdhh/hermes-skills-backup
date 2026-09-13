#!/bin/sh
# git clean filter: 把机队凭据明文替换为占位符（仅影响 git 存储的内容，本地文件不动）
sed -e 's/ubuntu\/ubuntu/${ROBOT_CREDS}/g' \
    -e 's/${ROBOT_CREDS_PLAIN}/${ROBOT_CREDS_PLAIN}/g' \
    -e 's/PASSWORD = os.environ["ROBOT_PASSWORD"]/PASSWORD = os.environ["ROBOT_PASSWORD"]/g'
