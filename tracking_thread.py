from PyQt5 import QtCore as QtCore
from PyQt5 import QtWidgets as QtWidgets
from PyQt5 import QtGui as QtGu
from PyQt5.QtCore import *
import sys
import cv2
import collections
import math
import pyautogui

class TrackingThread(QtCore.QThread):

    request_button_centers = pyqtSignal()
    move_cursor_to_button = pyqtSignal(tuple)

    def __init__(self, parent=None):
        super(TrackingThread, self).__init__(parent)

        #Values required to run thread
        self.mutex = QtCore.QMutex()
        self.condition = QtCore.QWaitCondition()
        self.restart = False
        self.abort = False
        self.loop_count = 0

        #Centers of buttons used for snapping
        self.button_centers = []

        #Connect signal to update buttons to setButtonCenters

    def __del__(self):
        self.mutex.lock()
        self.abort = True
        self.condition.wakeOne()
        self.mutex.unlock()

        self.wait()

    @pyqtSlot(list)
    def setButtonCenters(self, centers):
        self.button_centers = centers
        for center in centers:
            print(center)


    def startProcessing(self):
        locker = QtCore.QMutexLocker(self.mutex)

        if not self.isRunning():
            self.start(QtCore.QThread.LowPriority)
        else:
            self.restart = True
            self.condition.wakeOne()

    def findClosestCenter(self, cursor_pos):
        """Used to figure out the closest button user is currently looking at"""
        magnitude_vectors = []
        #Calculate vector between eye cursor and each button
        for center in self.button_centers:
            b_x = center[0]
            b_y = center[1]
            c_x = cursor_pos[0]
            c_y = cursor_pos[1]

            delta_x = abs(c_x - b_x)/1000
            delta_y = abs(c_y - b_y)/1000

            mag = math.sqrt((math.pow(2,delta_x) + math.pow(2,delta_y)))
            entry = (mag, center)
            magnitude_vectors.append(entry)

        if self.loop_count < 1:
            print(magnitude_vectors)
            self.loop_count += 1

        #See which one is closest
        closest_entry = magnitude_vectors[0]
        for entry in magnitude_vectors:
            if(entry[0] < closest_entry[0]):
                closest_entry = entry
        if self.loop_count < 2:
            print("Closest:")
            print(closest_entry)

        #Emit signal to tell gui thread to move cursor
        self.move_cursor_to_button.emit(closest_entry[1])

    def findEyeCenter(self,gray_eye, thresh_eye):
        """ findEyeCenter: approximates the center of the pupil by selecting
            the darkest point in gray_eye that is within the blob detected in
            thresh_eye

            args:
                - gray_eye: gray-scale image of eye
                - thresh_eye: binary eye image with contours filled in"""

        dims = gray_eye.shape # get shape image
        minBlack = 300
        pupil = [0, 0]

        for i in range(dims[0]):
            for j in range(dims[1]):
                if thresh_eye[i][j]:
                    if gray_eye[i][j] < minBlack:
                        minBlack = gray_eye[i][j]
                        pupil[0] = i
                        pupil[1] = j

        return pupil

    def getPupilAvgFromFace(self,gray_face, eyes, x, y, w, h):
        """
        getPupilAvgFromFace(gray_face, eyes, x, y, w, h): Takes a grey version of face image,
        a list of eyes, and the x, y, w, h, coordinates of the face. Returns a list [x, y] for
        the average between the eyes contained in the list.
        """
        pupil_avg = [0,0]
        for (ex,ey,ew,eh) in eyes:
            gray_eye = gray_face[ey:ey+eh, ex:ex+ew] # get eye
            #eye = face[ey:ey+eh, ex:ex+ew]

            # apply gaussian blur to image
            blur = cv2.GaussianBlur(gray_eye, (15,15), 3*gray_eye.shape[0])
            retval, thresh = cv2.threshold(~blur, 150, 255, cv2.THRESH_BINARY)
            _,contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(thresh, contours, -1, (255, 255, 255), -1)
            #circles = cv2.HoughCircles(thresh, cv2.cv.CV_HOUGH_GRADIENT, 1, 1)
            pupil = self.findEyeCenter(gray_eye, thresh)

            # Uncomment to highlight individual pupils.
            cv2.circle(gray_face, (int(pupil[1] + ex + x), int(pupil[0] + ey + y)), 2, (0,255,0), -1)

            pupil_avg[0] += pupil[1] + ex + x;
            pupil_avg[1] += pupil[0] + ey + y;

        # Compute pupil average
        pupil_avg = [x / len(eyes) for x in pupil_avg]

        return pupil_avg

    def run(self):
        self.request_button_centers.emit()
        while True:
            face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
            eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')
            left_eye_cascade = cv2.CascadeClassifier('haarcascade_lefteye_2splits.xml')
            right_eye_cascade = cv2.CascadeClassifier('haarcascade_righteye_2splits.xml')

            if face_cascade.empty():
                print("did not load face classifier.")

            if eye_cascade.empty():
                print("did not load eye classifier.")

            if left_eye_cascade.empty():
                print("did not load left eye classifier.")

            if right_eye_cascade.empty():
                print("did not load right eye classifier.")

            #cap = cv2.videocapture('/users/bsoper/movies/eye_tracking/cal_1.mov')
            cap = cv2.VideoCapture(0)

            #center_count = 0
            have_center = False
            center = [0,0]
            rolling_pupil_avg = collections.deque(maxlen=5)
            blink_count = 0
            x_scale_factor = 60
            y_scale_factor = 60
            frame_count = 0

            while(cap.isOpened()):
                # pull video frame
                ret, img = cap.read()
                img = cv2.flip(img,1)

                #Greyscale
                if(img.size == 0):
                    continue

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # get faces
                face_scale_factor = 1.3
                face_min_neighbors = 5
                faces = face_cascade.detectMultiScale(img, face_scale_factor, face_min_neighbors)

                for (x,y,w,h) in faces:
                    # Pull face sub-image
                    gray_face = gray[y:y+h, x:x+w]
                    face = img[y:y+h, x:x+w]

                    eyes = eye_cascade.detectMultiScale(gray_face, 3.0, 5) # locate eye regions
                    left_eye = left_eye_cascade.detectMultiScale(gray_face, 3.0, 5) # locate left eye regions
                    right_eye = right_eye_cascade.detectMultiScale(gray_face, 3.0, 5) # locate left eye regions

                    # This ignores any frames where we have detected too few or too many eyes.
                    # This generally won't filter out too many frames, as most detect eyes pretty well.
                    # This is needed so we don't get bad data in our rolling averages.
                    # Sometimes it will detect both eyes as right and left, so we just want to check if
                    # it detected none, or more than two of each.
                    if (len(left_eye) > 0 and len(left_eye) <= 2 and
                        len(right_eye) > 0 and len(right_eye) <= 2):
                        if len(eyes) == 0:
                            blink_count += 1
                            continue
                        elif len(eyes) == 2:
                            if blink_count >= 7:
                                print('\nLong Blink', blink_count)
                                pyautogui.click()
                                blink_count = 0
                            elif blink_count >= 2:
                                print('\nBlink', blink_count)
                                pyautogui.click()
                                blink_count = 0
                            else:
                                blink_count = 0

                    if len(eyes) != 2:
                        continue

                    # Uncomment to add boxes around face and eyes.
                    cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)
                    color_face = img[y:y+h, x:x+w]
                    for (ex,ey,ew,eh) in eyes:
                        cv2.rectangle(color_face,(ex,ey),(ex+ew,ey+eh),(0,255,0),2)

                    pupil_avg = self.getPupilAvgFromFace(gray_face, eyes, x, y, w, h)

                    if have_center == False:
                        center = pupil_avg
                        have_center = True

                    # Highlight center.
                    if have_center:
                        cv2.circle(img, (int(center[0]), int(center[1])), 2, (255,0,0), -1)
                    x_scaled = center[0] + (pupil_avg[0] - center[0]) * x_scale_factor
                    y_scaled = center[1] + (pupil_avg[1] - center[1]) * y_scale_factor

                    rolling_pupil_avg.appendleft((x_scaled, y_scaled))

                    avgs = (sum(a) for a in zip(*rolling_pupil_avg))
                    avgs = [a / len(rolling_pupil_avg) for a in avgs]

                    cv2.circle(img, (int(avgs[0]), int(avgs[1])), 5, (0,0,255), -1)

                    #Move mouse cursor
                    self.findClosestCenter((avgs[0], avgs[1]))

                    #pyautogui.moveTo(avgs[0], avgs[1])

                    #if avgs[0] - center[0] < -200:
                        #pyautogui.moveTo(200, 500)
                        #print('Left')
                    #elif avgs[0] - center[0] > 200:
                        #pyautogui.moveTo(1200, 500)
                        #print('Right')

                    # Uncomment to see location without averaging
                    #cv2.circle(img, (x_scaled, y_scaled), 5, (255,0,255), -1)

                    # Uncomment to show unscaled movement of average.
                    #x = center[0] + (pupil_avg[0] - center[0])
                    #y = center[1] + (pupil_avg[1] - center[1])
                    #cv2.circle(img, (x, y), 2, (0,255,0), -1)

                #cv2.imshow('frame', img)

                #if cv2.waitKey(1) & 0xFF == ord('c'):
                #    center = pupil_avg

                #if cv2.waitKey(1) & 0xFF  == ord('k'):
                #    cap.release()
                #    break

                #Mutex stuff
                #self.mutex.lock()
                #if not self.restart:
                #    self.condition.wait(self.mutex)
                #self.restart = False
                #self.mutex.unlock()

            # cleanup
            #cap.release()
            #cv2.destroyAllWindows()