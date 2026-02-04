import cv2
import numpy as np
import template

#run out of repo root with "python debug_orange_probe.py"

def main():
    region = template.roi_regions["orange"]
    roi = template._grab_region(region)  # uses screen.get_screen_roi() scaling/offset

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower = np.array([0, 60, 60])
    upper = np.array([55, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    hits = int(np.count_nonzero(mask))
    area = int(mask.size)
    min_hits = max(6, int(area * 0.01))

    # Stats for diagnosis
    h = hsv[:, :, 0]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    print(f"ROI shape: {roi.shape[1]}x{roi.shape[0]}")
    print(f"Mask hits: {hits} / {area} (min_hits={min_hits}) => {'PASS' if hits >= min_hits else 'FAIL'}")
    print(f"H min/mean/max: {int(h.min())} / {float(h.mean()):.2f} / {int(h.max())}")
    print(f"S min/mean/max: {int(s.min())} / {float(s.mean()):.2f} / {int(s.max())}")
    print(f"V min/mean/max: {int(v.min())} / {float(v.mean()):.2f} / {int(v.max())}")

    cv2.imwrite("orange_probe_roi.png", roi)
    cv2.imwrite("orange_probe_mask.png", mask)
    print("Wrote: orange_probe_roi.png, orange_probe_mask.png")

if __name__ == "__main__":
    main()
