import QtQuick
import QtMultimedia

Item {
    id: soundEngine

    property bool enabled: true

    SoundEffect {
        id: clickSound
        source: "qrc:/sounds/click.wav"
        volume: 0.5
    }

    SoundEffect {
        id: sendSound
        source: "qrc:/sounds/send.wav"
        volume: 0.6
    }

    SoundEffect {
        id: replySound
        source: "qrc:/sounds/reply.wav"
        volume: 0.6
    }

    function playClick() {
        if (enabled) clickSound.play()
    }

    function playSend() {
        if (enabled) sendSound.play()
    }

    function playReply() {
        if (enabled) replySound.play()
    }
}
