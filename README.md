# TechnoBulb
The bulb's color will change with the output stream of your device (e.g. music), pretty cool right?

# Setup

This app was made for _LEDVANCE RGBW 806lm 9w E27_

```
  $ pip install pytuya soundcard scapy PySide6 numpy
  $ cd TechnoBulb
  $ python techno_bulb.py
```

![image](https://github.com/FLOCK4H/TechnoBulb/assets/161654571/ea1b9f63-d9ac-456d-a641-28c8aaa3e5b3)

The GUI is for simply pausing the algorithm, press 'P' to pause the color at current frame.

# About

This app catches the sound stream of the default output device on the lower level, means it captures audio before it gets to the speakers.
The delay is also minimal, very difficult to notice.
The audio is then converted into magnitude and frequency using FFT (Fast Fourier Transformation) and is applied on the color gradient scheme to finally send the right color via request to the bulb.
