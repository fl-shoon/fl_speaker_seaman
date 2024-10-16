import cv2
import time

def test_camera_headless():
    # Open the first camera device (usually the Pi camera)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open camera.")
        return
    
    print("Camera opened successfully. Starting to capture frames...")
    
    try:
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < 10:  # Run for 10 seconds
            # Capture frame-by-frame
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Can't receive frame. Exiting ...")
                break
            
            frame_count += 1
            
            # Optional: You could save a frame here if you want to verify image capture
            # cv2.imwrite(f'frame_{frame_count}.jpg', frame)
            
            # Print dimensions of the frame
            height, width, channels = frame.shape
            print(f"Captured frame {frame_count}: {width}x{height} ({channels} channels)")
            
            # Optional: add a small delay to reduce CPU usage
            time.sleep(0.1)
    
    finally:
        # When everything done, release the capture
        cap.release()
        print(f"Camera test completed. Captured {frame_count} frames in 10 seconds.")

if __name__ == "__main__":
    test_camera_headless()