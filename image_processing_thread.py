import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread as QThread
import sys

class imageProcessingThread(QThread):
	def __init__(self):
		QThread.__init__()

	def __del__(self):
		self.wait()

	def run(self):
		detectPupils()

	def findEyeCenter(gray_eye, thresh_eye):
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

	def detectPupils():
		face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
		eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

		if face_cascade.empty():
			print("did not load face classifier")

		if eye_cascade.empty():
			print("did not load eye classifier")

		#cap = cv2.VideoCapture('/Users/bsoper/Movies/eye_tracking/face.mov')
		cap = cv2.VideoCapture(0)

		while(cap.isOpened()):

			# pull video frame
			ret, img = cap.read()
			img = cv2.flip(img,1)

			#Greyscale
			gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

			# get faces
			face_scale_factor = 1.3
			face_min_neighbors = 5
			faces = face_cascade.detectMultiScale(img, face_scale_factor, face_min_neighbors)

			for (x,y,w,h) in faces:
				# pull face sub-image
				gray_face = gray[y:y+h, x:x+w]
				face = img[y:y+h, x:x+w]

				#eyes = eye_cascade.detectMultiScale(gray_face) # locate eye regions
				eye_scale_factor = 3.0
				eye_min_neighbors = 5

				#Locate Eye Regions
				eyes = eye_cascade.detectMultiScale(gray_face, eye_scale_factor, eye_min_neighbors)

				if len(eyes) == 0:
					continue

				#cv2.rectangle(img,(x,y),(x+w,y+h),(255,0,0),2)                              #####
				#color_face = img[y:y+h, x:x+w]                                              #####
				#for (ex,ey,ew,eh) in eyes:                                                  #####
				#    cv2.rectangle(color_face,(ex,ey),(ex+ew,ey+eh),(0,255,0),2)             #####


				pupil_avg = [0,0]
				#"""
				for (ex,ey,ew,eh) in eyes:
					gray_eye = gray_face[ey:ey+eh, ex:ex+ew] # get eye
					#eye = face[ey:ey+eh, ex:ex+ew]

					# apply gaussian blur to image
					blur = cv2.GaussianBlur(gray_eye, (15,15), 3*gray_eye.shape[0])

					retval, thresh = cv2.threshold(~blur, 150, 255, cv2.THRESH_BINARY)

					_, contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

					cv2.drawContours(thresh, contours, -1, (255, 255, 255), -1)
					#circles = cv2.HoughCircles(thresh, cv2.cv.CV_HOUGH_GRADIENT, 1, 1)

					pupil = findEyeCenter(gray_eye, thresh)

					#cv2.circle(eye, pupil, 0, (0,255,0), -1)

					#cv2.circle(img, (pupil[1] + ex + x, pupil[0] + ey + y), 2, (0,255,0), -1)

					pupil_avg[0] += pupil[1] + ex + x;
					pupil_avg[1] += pupil[0] + ey + y;
				#"""

				pupil_avg = [x / len(eyes) for x in pupil_avg]

				#Plot pupil on screen
				pupil_color = (0,255,0)
				cv2.circle(img, (int(pupil_avg[0]), int(pupil_avg[1])), 2, pupil_color, -1)

				#Test movement of mouse to pupil location
				pyautogui.moveTo(int(pupil_avg[0]), int(pupil_avg[1]))

				#Sleep thread
				self.sleep(2)






			cv2.imshow('frame', img)

			if cv2.waitKey(1) & 0xFF == ord('q'):
				cv2.imwrite('bad_eye.jpg', img)
				break

			if cv2.waitKey(1) & 0xFF  == ord('k'):
				cap.release()
				break
		# cleanup
		cap.release()
		cv2.destroyAllWindows()
