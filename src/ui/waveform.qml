import QtQuick 2.15

Canvas {
    id: waveform
    width: parent.width * 0.8
    height: 80

    property var samples: []

    onPaint: {
        var ctx = getContext("2d")
        ctx.fillStyle = "#101018"
        ctx.fillRect(0, 0, width, height)

        if (!samples || samples.length === 0)
            return;

        ctx.strokeStyle = "#66aaff"
        ctx.lineWidth = 2
        ctx.beginPath()

        var step = width / samples.length
        for (var i = 0; i < samples.length; i++) {
            var y = height/2 + samples[i] * (height/2 - 5)
            if (i === 0)
                ctx.moveTo(i * step, y)
            else
                ctx.lineTo(i * step, y)
        }
        ctx.stroke()
    }
}
