'''
Python script for parsing the KITTI Dataset
'''
import cv2 as cv
import os
import event
import sys
import glob
import numpy as np
import math

class dataHandler():

    train_img_dir = ""
    train_label_dir = ""
    test_img_dir = ""

    train_arr = []
    test_arr = []

    train_unused = []
    test_unused = []

    sx = -1
    sy = -1

    epochs_elapsed = 0
    batches_elapsed = 0

    NUM_CLASSES = 4
    IMGDIMS = (1242, 375)

    def seperate_labels(self, arr):
        arr = np.array(arr)
        B = self.B
        C = self.NUM_CLASSES
        x = arr[:,:,:B]
        y = arr[:,:,B:2*B]
        w = arr[:,:,2*B:3*B]
        h = arr[:,:,3*B:4*B]
        conf = arr[:,:,4*B:5*B]
        classes = arr[:,:,5*B:(5+C)*B]
        return x,y,w,h,conf,classes

    def dispImage(self, image, boundingBoxes = None, drawTime = 1000):
        im = image
        B = self.B
        if boundingBoxes is not None:
            x_,y_,w_,h_,_,classes_ = self.seperate_labels(boundingBoxes)
            for x in range(0,x_.shape[0]):
                for y in range(0,x_.shape[1]):
                    for i in range(B):
                        if x_[x][y][i] is not None:
                            bounds = self.xywh_to_p1p2([x_[x][y][i], y_[x][y][i], w_[x][y][i], h_[x][y][i]], x, y)
                            classtype = self.onehot_to_text(classes_[x][y][i:i+4])
                            cv.rectangle(im, (bounds[0], bounds[1]), (bounds[2], bounds[3]), (255, 0, 0), 3)
                            cv.putText(im, classtype, (bounds[0], bounds[1]-5), cv.FONT_HERSHEY_PLAIN, 1.0, (0, 0, 255))
        cv.imshow("frame.jpg", im)
        cv.waitKey(drawTime)

    def onehot_to_text(self, arr):
        if arr[0] == 1:
            return "Misc. Vehicle"
        if arr[1] == 1:
            return "Pedestrian"
        if arr[2] == 1:
            return "Cyclist"
        if arr[3] == 1:
            return "Car"
        else:
            return "unknwn"

    def xywh_to_p1p2(self, inp, x_, y_):
        x, y, w, h = inp
        p1x = x - (w / 2) + x_ * (self.IMGDIMS[1] / self.sx)
        p1y = y - (h / 2) + y_ * (self.IMGDIMS[1] / self.sx)
        p2x = x + (w / 2) + x_ * (self.IMGDIMS[1] / self.sx)
        p2y = y + (h / 2) + y_ * (self.IMGDIMS[1] / self.sx)
        arr = [p1x, p1y, p2x, p2y]
        return [int(x) for x in arr]

    def get_img(self, num_arr):
        refdims = {}
        imgs = None
        for indice in num_arr:
            imgdir = self.train_img_dir + "/" + self.train_arr[indice] + ".png"
            im = cv.imread(imgdir)
            if not im.shape[:2] == (self.IMGDIMS[1], self.IMGDIMS[0]):
                im = cv.resize(im, (self.IMGDIMS[0], self.IMGDIMS[1]), interpolation = cv.INTER_CUBIC)
            refx = np.random.randint(self.IMGDIMS[0]-self.IMGDIMS[1])
            crop = im[:, refx:refx+self.IMGDIMS[1]]
            crop = (crop / 255.) * 2. - 1.
            if imgs is not None:
                #print(imgs.shape, crop[np.newaxis, :].shape)
                imgs = np.vstack((imgs, crop[np.newaxis, :]))
            else:
                imgs = crop[np.newaxis, :]
            refdims[indice]= [refx, refx+self.IMGDIMS[1]]
        return imgs, refdims

    def get_indices(self, batchsize, training = True):
        finarr = []
        if training:
            if len(self.train_unused) < batchsize:
                finarr = self.train_unused
                self.train_unused = np.arange(len(self.train_arr))
                np.random.shuffle(self.train_unused)
                self.epochs_elapsed += 1
            else:
                finarr = self.train_unused[:batchsize]
                self.train_unused = self.train_unused[batchsize:]
            self.batches_elapsed += 1
        else:
            pass
        return finarr

    def p1p2_to_xywh(self, p1x, p1y, p2x, p2y, xref):
        w = (p2x - p1x)
        h = (p2y - p1y)
        x = p1x + (w / 2) - xref
        y = p1y + (h / 2)
        arr = [x, y, w, h]
        return [round(x,2) for x in arr]

    def getBox(self, x, y):
        col = int(math.floor(x / self.IMGDIMS[1] * (self.sx-1)))
        row = int(math.floor(y / self.IMGDIMS[1] * (self.sy-1)))
        return [row,col]

    def get_label(self, num_arr, refdims):
        labels = []
        for indice in num_arr:
            with open(self.train_label_dir + "/" + self.train_arr[indice] + ".txt", "r") as f:
                #grid = [[[None for x in range(self.B*(self.NUM_CLASSES + 5))] for x in range(self.sx)] for x in range(self.sy)]
                grid = np.zeros([self.sx, self.sy, self.B*(self.NUM_CLASSES + 5)])
                for line in f:
                    box_det = line.split(" ")
                    C = [0.] * self.NUM_CLASSES
                    keep = True

                    if box_det[0] == "Car":
                        C[3] = 1.
                    elif box_det[0] == "Pedestrian":
                        C[1] = 1.
                    elif box_det[0] == "Cyclist":
                        C[2] = 1.
                    elif box_det[0] == "Truck" or box_det[0] == "Van":
                        C[0] = 1.
                    else:
                        keep = False

                    p1x, p1y, p2x, p2y = [float(x) for x in box_det[4:8]]
                    xywh = self.p1p2_to_xywh(p1x, p1y, p2x, p2y, refdims[indice][0])
                    if (xywh[0] > 0 and xywh[0] < self.IMGDIMS[1]) and keep:
                        cellx, celly = self.getBox(xywh[0], xywh[1])

                        xywh[0] = xywh[0] - cellx * (self.IMGDIMS[1] / self.sx)
                        xywh[1] = xywh[1] - celly * (self.IMGDIMS[1] / self.sy)

                        argcheck = 0
                        for i in range(0, self.B):
                            if argcheck == 0 and grid[cellx][celly][i*(self.NUM_CLASSES + 5)] == None:
                                grid[cellx][celly][i] = xywh[0]
                                grid[cellx][celly][self.B + i] = xywh[1]
                                grid[cellx][celly][2*self.B + i] = xywh[2]
                                grid[cellx][celly][3*self.B + i] = xywh[3]
                                grid[cellx][celly][4*self.B + i] = 1.
                                grid[cellx][celly][5*self.B + i: 5*self.B + i + 4] = C
                                argcheck = 1
                        #boxes.append(xywh + C)
            labels.append(grid)
        return labels

    def minibatch(self, batchsize, training = True):
        indices = self.get_indices(batchsize, training = training)
        imgs, refdims = self.get_img(indices)
        labels = self.get_label(indices, refdims)
        return imgs, labels

    def __init__(self, train, test, NUM_CLASSES = 4, B = 3, sx = 5, sy = 5):
        if os.path.exists(train) and os.path.exists(test):
            self.train_img_dir = train + "/image"
            self.train_label_dir = train + "/label"
            self.test_img_dir = test + "/image"

            self.NUM_CLASSES = NUM_CLASSES
            self.B = B

            self.sx = sx
            self.sy = sy

            self.train_arr = [x[:-4] for x in os.listdir(self.train_img_dir)]
            self.test_arr = [x[:-4] for x in os.listdir(self.test_img_dir)]

            self.train_unused = np.arange(len(self.train_arr))
            np.random.shuffle(self.train_unused)
            self.test_unused = np.arange(len(self.test_arr))
            np.random.shuffle(self.test_unused)
        else:
            print("Invalid directory! Check path.")

    def __str__(self):
        traindatalen = "Number of training examples: " + str(len(self.train_arr)) + "\n"
        testdatalen = "Number of testing examples: " + str(len(self.test_arr)) + "\n"
        unusedlentraining = "Number of training examples remaining: " + str(len(self.train_unused)) + "\n"
        currbatches = "Number of batches elapsed: " + str(self.batches_elapsed) + "\n"
        currepochs = "Number of epochs elapsed: " + str(self.epochs_elapsed) + "\n"
        return "[OK] Loading \n" + traindatalen + testdatalen + unusedlentraining + currbatches + currepochs
