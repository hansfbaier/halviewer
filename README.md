# halviewer

graphical halviewer for linuxcnc

reads the hal from running linuxcnc session and shows the signals in realtime

## GUI

double-click on title to group/ungroup nodes

double-click on pins to:

* change the value (setp) / maked with ">...<"
* add a linechart to see the value-changes

you can move the nodes to customize the layout (use STRG to select multiple nodes)

Mouse-Wheel to Zoom In/Out


![screenshot](./halviewer.png)

## quickstart
install depends
```
apt-get install python3-pyqt5 python3-graphviz
```

before running halviewer, you need to run linuxcnc, than:
```
python3 halviewer.py
```

if you want to use pyqt6 support:
```
python3 halviewer.py -6
```


[![HalViewer](https://img.youtube.com/vi/Ma7J_gvicco/0.jpg)](https://www.youtube.com/watch?v=Ma7J_gvicco&feature=youtu.be "HalViewer")
