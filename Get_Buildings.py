import tensorflow as tf
import numpy as np
from osgeo import gdal, osr, gdalconst
import argparse
import sys
import warnings


def load_image(img,input_shape=(224,224)):
    '''
    Loads RGB arrays of images from a raster. Then pads with zeros to ensure correct size with 
    '''
    src = gdal.Open(img,gdalconst.GA_ReadOnly)
    red = np.array(src.GetRasterBand(1).ReadAsArray(),dtype=np.float32)/2047.0
    green = np.array(src.GetRasterBand(2).ReadAsArray(),dtype=np.float32)/2047.0
    blue = np.array(src.GetRasterBand(3).ReadAsArray(),dtype=np.float32)/2047.0
    width = red.shape[1]
    height = red.shape[0]
    orig_size = (height,width)
    if np.mod(width,input_shape[1]) != 0:
        n_images_x = int(np.floor(width/input_shape[1]))+1
        dx = n_images_x*input_shape[1] - width
    else:
        dx = 0
    if np.mod(height,input_shape[0]) != 0:
        n_images_y = int(np.floor(height/input_shape[0]))+1
        dy = n_images_y*input_shape[0] - height
    else:
        dy = 0
    red = np.pad(red,((0,dy),(0,dx)),constant_values=((0,0),(0,0)))
    green = np.pad(green,((0,dy),(0,dx)),constant_values=((0,0),(0,0)))
    blue = np.pad(blue,((0,dy),(0,dx)),constant_values=((0,0),(0,0)))
    return red,green,blue,orig_size

def predict_segment(img_segment,model):
    prediction = model.predict(img_segment)
    return prediction

def predict_buildings(model,img,input_shape=(224,224)):
    #height x width
    red_array,green_array,blue_array,img_size = load_image(img,input_shape)
    prediction = np.zeros(red_array.shape)
    train_stack = np.dstack((red_array,green_array,blue_array))
    train_array = tf.expand_dims(tf.convert_to_tensor(train_stack),axis=0)
    n_images_x = int(train_array.shape[2]/input_shape[1])
    n_images_y = int(train_array.shape[1]/input_shape[0])
    n_images_total = n_images_x * n_images_y
    count = 0
    print('Predicting buildings...')
    for i in range(n_images_x):
        print(f'{i}/{n_images_x}')
        for j in range(n_images_y):
            count = count+1
            sys.stdout.write('\r')
            n_progressbar = (count) / n_images_total
            sys.stdout.write("[%-20s] %d%%" % ('='*int(20*n_progressbar), 100*n_progressbar))
            sys.stdout.flush()
            train_segment = train_array[:,j*input_shape[0]:(j+1)*input_shape[0],i*input_shape[1]:(i+1)*input_shape[1],:]
            prediction_segment = model.predict(train_segment).squeeze()
            prediction[j*input_shape[0]:(j+1)*input_shape[0],i*input_shape[1]:(i+1)*input_shape[1]] = prediction_segment
    prediction = prediction[:img_size[0],:img_size[1]]
    return prediction

def main():
    warnings.simplefilter(action='ignore')
    parser = argparse.ArgumentParser()
    parser.add_argument('--model',help='Path to input ML model for building detection.')
    parser.add_argument('--image',help='Path to input image to run building detection on.')
    
    '''
    input_model = '/media/heijkoop/DATA/Dropbox/TU/PhD/Machine_Learning/ResUNet_Building_Detection/resunet_model_wv_pansharpened'
    img = '/home/heijkoop/Desktop/tmp/Building_Detection/WV03_20200402_104001005A87A100_104001005B0CCA00_pansharpened_orthorectified.tif'

    input_model = '/BhaltosMount/Bhaltos/EDUARD/Projects/Machine_Learning/WV_PanSharpened/Models/resunet_model_wv_pansharpened'
    img = '/BhaltosMount/Bhaltos/EDUARD/Projects/Machine_Learning/WV_PanSharpened/Testing/Training_Data/WV03_20200402_104001005A87A100_104001005B0CCA00_pansharpened_orthorectified.tif'
    '''

    THRESHOLD = 0.7

    args = parser.parse_args()
    input_model = args.model
    img = args.image
    model = tf.keras.models.load_model(input_model)
    src = gdal.Open(img,gdalconst.GA_ReadOnly)
    prediction = predict_buildings(model,img)
    prediction_binary = (prediction > THRESHOLD).astype(int)

    # Create output raster
    driver = gdal.GetDriverByName('GTiff')
    out_raster = driver.Create(img.replace('.tif','_prediction.tif').replace('Training_Data','Prediction'),prediction_binary.shape[1],prediction_binary.shape[0],1,gdal.GDT_Byte)
    out_raster.SetGeoTransform(src.GetGeoTransform())
    out_raster.SetProjection(src.GetProjection())
    out_raster.GetRasterBand(1).WriteArray(prediction_binary)
    out_raster.FlushCache()
    out_raster = None


if '__name__' == '__main__':
    main()