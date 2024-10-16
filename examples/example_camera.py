import cv2
import time

def test_camera():
    # Open the first camera device (usually the Pi camera)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return
    
    print("Camera opened successfully. Starting video stream...")
    
    try:
        while True:
            # Capture frame-by-frame
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Can't receive frame (stream end?). Exiting ...")
                break
            
            # Display the resulting frame
            cv2.imshow('Raspberry Pi Camera Test', frame)
            
            # Press 'q' to quit
            if cv2.waitKey(1) == ord('q'):
                break
            
            # Optional: add a small delay to reduce CPU usage
            time.sleep(0.01)
    
    finally:
        # When everything done, release the capture
        cap.release()
        cv2.destroyAllWindows()
        print("Camera test completed.")

if __name__ == "__main__":
    test_camera()