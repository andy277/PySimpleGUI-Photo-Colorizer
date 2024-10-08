import numpy as np
import os
import cv2

class Colorizer:
    def __init__(self, prototxt, model, points):

        # prototxt = r'../model/colorization_deploy_v2.prototxt'
        # model = r'../model/colorization_release_v2.caffemodel'
        # points = r'../model/pts_in_hull.npy'
        points = os.path.join(os.path.dirname(__file__), points)
        prototxt = os.path.join(os.path.dirname(__file__), prototxt)
        model = os.path.join(os.path.dirname(__file__), model)
        if not os.path.isfile(model):
            print('Missing model file', 'You are missing the file "colorization_release_v2.caffemodel"',
                              'Download it and place into your "model" folder',
                              'You can download this file from this location:\n',
                              r'https://www.dropbox.com/s/dx0qvhhp5hbcx7z/colorization_release_v2.caffemodel?dl=1')
            exit()
        self.net = cv2.dnn.readNetFromCaffe(prototxt, model)  # load model from disk
        pts = np.load(points)

        # add the cluster centers as 1x1 convolutions to the model
        class8 = self.net.getLayerId("class8_ab")
        conv8 = self.net.getLayerId("conv8_313_rh")
        pts = pts.transpose().reshape(2, 313, 1, 1)
        self.net.getLayer(class8).blobs = [pts.astype("float32")]
        self.net.getLayer(conv8).blobs = [np.full([1, 313], 2.606, dtype="float32")]

    def colorize_image(self, image_filename=None, cv2_frame=None):
        """
        Where all the magic happens.  Colorizes the image provided. Can colorize either
        a filename OR a cv2 frame (read from a web cam most likely)
        :param image_filename: (str) full filename to colorize
        :param cv2_frame: (cv2 frame)
        :return: Tuple[cv2 frame, cv2 frame] both non-colorized and colorized images in cv2 format as a tuple
        """
        # load the input image from disk, scale the pixel intensities to the range [0, 1], and then convert the image from the BGR to Lab color space
        image = cv2.imread(image_filename) if image_filename else cv2_frame
        scaled = image.astype("float32") / 255.0
        lab = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)

        # resize the Lab image to 224x224 (the dimensions the colorization network accepts), split channels, extract the 'L' channel, and then perform mean centering
        resized = cv2.resize(lab, (224, 224))
        L = cv2.split(resized)[0]
        L -= 50

        # pass the L channel through the network which will *predict* the 'a' and 'b' channel values
        'print("[INFO] colorizing image...")'
        self.net.setInput(cv2.dnn.blobFromImage(L))
        ab = self.net.forward()[0, :, :, :].transpose((1, 2, 0))

        # resize the predicted 'ab' volume to the same dimensions as our input image
        ab = cv2.resize(ab, (image.shape[1], image.shape[0]))

        # grab the 'L' channel from the *original* input image (not the resized one) and concatenate the original 'L' channel with the predicted 'ab' channels
        L = cv2.split(lab)[0]
        colorized = np.concatenate((L[:, :, np.newaxis], ab), axis=2)

        # convert the output image from the Lab color space to RGB, then clip any values that fall outside the range [0, 1]
        colorized = cv2.cvtColor(colorized, cv2.COLOR_LAB2BGR)
        colorized = np.clip(colorized, 0, 1)

        # the current colorized image is represented as a floating point data type in the range [0, 1] -- let's convert to an unsigned 8-bit integer representation in the range [0, 255]
        colorized = (255 * colorized).astype("uint8")
        return image, colorized