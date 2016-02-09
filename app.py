from flask import Flask, jsonify, request, send_file
from werkzeug import secure_filename
import config as cfg
import boto3, os, time
from boto3.s3.transfer import S3Transfer
from uuid import uuid1
from flask_swagger import swagger
import os, glob
import threading
from PIL import Image

AWS_BUCKET = "vt-storage"
app = Flask("vt-storage-server")
app.debug = True

# upload image api
@app.route("/upload", methods=['POST'])
def upload():
    """
    Upload files
    ---
    tags:
        - Files
    consumes: "multipart/form-data"
    parameters:
        -   name: files[]
            in: formData
            required: true
            paramType: body
            dataType: file
            type: file

    responses:
        200:
            description: Returns album_id after upload
        401:
            description: Unauthorized
        400:
            description: Bad Request
        500:
            description: Server Internal error
    """
    upload_file = request.files.get("file")
    upload_fileext = get_file_extension(upload_file.filename)
    print "Request files ->", request.files
    print "File ->", upload_file
    print "File extension -> ", upload_fileext
    
    if upload_file and upload_fileext:
        filename = secure_filename(str(uuid1()).replace('-', '') + '.' + upload_fileext)
    
        dir_name = 'chat/'
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
    
        file_path = os.path.join(dir_name, filename)
    
        app.logger.info("Saving file: %s", file_path)
        # save to local 
        upload_file.save(file_path)
        
        # Create thumbnail first
        if upload_fileext in ['jpg', 'jpeg', 'png']:
            thread = threading.Thread(target=make_thumbnail, args=(file_path,))
            thread.start()

        transfer = S3Transfer(boto3.client('s3', cfg.AWS_REGION, aws_access_key_id=cfg.AWS_APP_ID,
            aws_secret_access_key=cfg.AWS_APP_SECRET))
    
        # Upload to S3
        transfer.upload_file(file_path, AWS_BUCKET, file_path)
        if os.path.exists(file_path):
            os.remove(file_path)

        bc = boto3.client('s3', cfg.AWS_REGION, aws_access_key_id=cfg.AWS_APP_ID, aws_secret_access_key=cfg.AWS_APP_SECRET)
        download_url = '{}/{}/{}'.format(bc.meta.endpoint_url, AWS_BUCKET, file_path)
        print "Returning download url", download_url
        # download_url = 'http://storage.drivers.uz/download/{}'.format(filename)
    
        return jsonify({'status': 'ok', 'url': download_url})
    else:
        return jsonify({'status': 'fail', 'detail': 'File cannot be read server'})

# down load image
@app.route("/download/<filename>", methods=['GET'])
def download(filename):
    try:
        key = 'chat/' + secure_filename(filename)
        UPLOAD_DIR = os.path.abspath(os.path.join(os.path.split(__file__)[0], ''))
        # get file from S3
        transfer = S3Transfer(boto3.client('s3', cfg.AWS_REGION, aws_access_key_id=cfg.AWS_APP_ID,
                    aws_secret_access_key=cfg.AWS_APP_SECRET))
        # download file from aws
        transfer.download_file(AWS_BUCKET, key, key)

        # return send_file(UPLOAD_DIR + "/" + key, mimetype='image/gif')
        return send_file(UPLOAD_DIR + "/" + key)
    except:
        sentry.captureException()

def make_thumbnail(file_path):
    size = 64, 64
    download_url = ''
    codec = 'jpeg'
    for infile in glob.glob(file_path):
        file, ext = os.path.splitext(infile)
        app.logger.info("Creating thumbnail for %s", file_path)
        im = Image.open(file_path)
        im.thumbnail(size)
        thumb_file_path = file + "_thumb" + ext
        if ext in ['jpeg', 'jpg']:
            codec = 'jpeg'
        elif ext == 'png':
            codec = 'png'

	im.save(thumb_file_path, codec)
        transfer = S3Transfer(boto3.client('s3', cfg.AWS_REGION, aws_access_key_id=cfg.AWS_APP_ID,
            aws_secret_access_key=cfg.AWS_APP_SECRET))
        transfer.upload_file(thumb_file_path, AWS_BUCKET, thumb_file_path)

# Swagger Doccument for API
@app.route('/docs')
def spec():
    swag = swagger(app)
    swag['info']['version'] = "1.0"
    swag['info']['title'] = "VT Storage Server"
    swag['basePath'] = "/"
    return jsonify(swag)

# Cross origin
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin','*')
    response.headers.add('Access-Control-Allow-Headers', "Authorization, Content-Type")
    response.headers.add('Access-Control-Expose-Headers', "Authorization")
    response.headers.add('Access-Control-Allow-Methods', "GET, POST, PUT, DELETE, OPTIONS")
    response.headers.add('Access-Control-Allow-Credentials', "true")
    response.headers.add('Access-Control-Max-Age', 60 * 60 * 24 * 20)
    return response

def get_file_extension(filename):
    if '.' in filename:
       return filename.rsplit('.', 1)[1]
    else:
       None

if (__name__ == "__main__" ):
    app.run('127.0.0.1')
