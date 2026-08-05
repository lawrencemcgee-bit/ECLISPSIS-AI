import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import QtMultimedia 5.15

Window {
    id: root
    visible: true
    title: "ECLIPSIS-AI"
    color: "#101018"

    // -----------------------------
    // Theme Loader
    // -----------------------------
    Loader {
        id: themeLoader
        source: "theme.qml"
        onLoaded: root.color = themeLoader.item.background
    }

    // -----------------------------
    // Sound Engine
    // -----------------------------
    Loader {
        id: soundLoader
        source: "sound_engine.qml"
        onLoaded: soundLoader.item.enabled = assistant.profile.preferences.enable_sound_effects
    }

    // -----------------------------
    // Orb
    // -----------------------------
    Loader {
        id: orbLoader
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 40
        source: "orb.qml"
        onLoaded: {
            StateBridge.stateChanged.connect(
                function(newState) { orbLoader.item.assistantState = newState }
            )
        }
    }

    // -----------------------------
    // Typing Indicator
    // -----------------------------
    Rectangle {
        id: typingBubble
        width: 80; height: 30; radius: 15
        color: "#303040"
        anchors.horizontalCenter: orbLoader.horizontalCenter
        anchors.top: orbLoader.bottom; anchors.topMargin: 8
        opacity: 0.0

        Row {
            anchors.centerIn: parent; spacing: 6
            Repeater {
                model: 3
                Rectangle {
                    width: 8; height: 8; radius: 4; color: "#ffffff"
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.2; to: 1.0; duration: 400 }
                        NumberAnimation { from: 1.0; to: 0.2; duration: 400 }
                    }
                }
            }
        }

        Behavior on opacity { NumberAnimation { duration: 200 } }

        Component.onCompleted: {
            StateBridge.typingChanged.connect(
                function(isTyping) { typingBubble.opacity = isTyping ? 1.0 : 0.0 }
            )
        }
    }

    // -----------------------------
    // Chat Timeline
    // -----------------------------
    ListView {
        id: chatList
        width: parent.width * 0.45
        height: parent.height * 0.55
        anchors.left: parent.left; anchors.leftMargin: 20
        anchors.top: orbLoader.bottom; anchors.topMargin: 40
        spacing: 10; clip: true
        model: StateBridge.chat

        delegate: Rectangle {
            width: chatList.width; color: "transparent"

            Column {
                anchors.left: sender == "assistant" ? parent.left : undefined
                anchors.right: sender == "user" ? parent.right : undefined

                Rectangle {
                    width: chatList.width * 0.8; radius: 12
                    color: sender == "assistant" ? "#303040" : "#4060ff"

                    Text {
                        anchors.fill: parent; anchors.margins: 12
                        text: model.text; color: "white"
                        wrapMode: Text.WordWrap; font.pixelSize: 16
                    }
                }
            }

            opacity: 0.0; y: 20
            Behavior on opacity { NumberAnimation { duration: 250 } }
            Behavior on y { NumberAnimation { duration: 250 } }

            Component.onCompleted: { opacity = 1.0; y = 0 }
        }

        Component.onCompleted: {
            StateBridge.outputUpdated.connect(function(text) {
                if (text === "__play_reply_sound__")
                    soundLoader.item.playReply()
            })
        }
    }

    // -----------------------------
    // Waveform
    // -----------------------------
    Loader {
        id: waveformLoader
        source: "waveform.qml"
        anchors.top: chatList.bottom; anchors.topMargin: 10
        anchors.left: chatList.left

        Component.onCompleted: {
            StateBridge.waveformUpdated.connect(
                function(samples) {
                    waveformLoader.item.samples = samples
                    waveformLoader.item.requestPaint()
                }
            )
        }
    }

    // -----------------------------
    // Controls Row
    // -----------------------------
    Row {
        id: controlsRow
        spacing: 16
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: waveformLoader.bottom; anchors.topMargin: 10

        ComboBox {
            id: agentDropdown
            width: 160
            model: ["onenote", "weather", "news"]
            currentIndex: model.indexOf(assistant.settings.last_agent)
            onCurrentTextChanged: {
                soundLoader.item.playClick()
                StateBridge.selectAgent(currentText)
            }
        }

        Rectangle {
            width: 80; height: 32; radius: 6
            color: "#00cc88"
            Text { anchors.centerIn: parent; text: "Mic"; color: "white" }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    soundLoader.item.playClick()
                    StateBridge.toggleMic()
                    StateBridge.updateWaveform()
                }
            }
        }

        Rectangle {
            width: 100; height: 32; radius: 6
            color: "#ffaa00"
            Text { anchors.centerIn: parent; text: "Theme"; color: "white" }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    soundLoader.item.playClick()
                    themeLoader.item.toggle()
                    root.color = themeLoader.item.background
                    toastLoader.item.show("Theme changed")
                }
            }
        }
    }

    // -----------------------------
    // Chat Input Row
    // -----------------------------
    Row {
        id: chatInputRow
        spacing: 10
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 20

        Rectangle {
            id: chatInputBox
            width: parent.width * 0.5; height: 40; radius: 8
            color: "#202030"

            TextInput {
                id: chatInput
                anchors.fill: parent; anchors.margins: 10
                color: "#ffffff"; font.pixelSize: 16
                placeholderText: "Type a message..."
                placeholderTextColor: "#808080"

                onTextChanged: StateBridge.updateDraft(text)
            }
        }

        Rectangle {
            id: sendButton
            width: 100; height: 40; radius: 8
            color: "#66aaff"

            Text { anchors.centerIn: parent; text: "Send"; color: "white" }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (chatInput.text.length > 0) {
                        soundLoader.item.playSend()
                        toastLoader.item.show("Message sent")
                        StateBridge.sendMessage(chatInput.text)
                        chatInput.text = ""
                    }
                }
            }
        }
    }

    // -----------------------------
    // Log Viewer
    // -----------------------------
    Loader {
        id: logViewerLoader
        source: "log_viewer.qml"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.verticalCenter: parent.verticalCenter
    }

    // -----------------------------
    // Settings Button
    // -----------------------------
    Rectangle {
        id: settingsButton
        width: 100; height: 32; radius: 6
        color: "#8888ff"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: parent.top; anchors.topMargin: 20

        Text { anchors.centerIn: parent; text: "Settings"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                settingsLoader.visible = !settingsLoader.visible
                StateBridge.setSettingsOpen(settingsLoader.visible)
                toastLoader.item.show("Settings " + (settingsLoader.visible ? "opened" : "closed"))
            }
        }
    }

    Loader {
        id: settingsLoader
        source: "settings_panel.qml"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: settingsButton.bottom; anchors.topMargin: 10
        visible: false
    }

    // -----------------------------
    // Profile Button
    // -----------------------------
    Rectangle {
        id: profileButton
        width: 100; height: 32; radius: 6
        color: "#55aa55"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: settingsButton.bottom; anchors.topMargin: 50

        Text { anchors.centerIn: parent; text: "Profile"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                profileLoader.visible = !profileLoader.visible
                StateBridge.setProfileOpen(profileLoader.visible)
                toastLoader.item.show("Profile panel " + (profileLoader.visible ? "opened" : "closed"))
            }
        }
    }

    Loader {
        id: profileLoader
        source: "profile_panel.qml"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: profileButton.bottom; anchors.topMargin: 10
        visible: false
    }

    // -----------------------------
    // Quick Panel
    // -----------------------------
    Loader {
        id: quickPanelLoader
        source: "quick_panel.qml"
        anchors.left: parent.left; anchors.leftMargin: 20
        anchors.bottom: parent.bottom; anchors.bottomMargin: 80
        visible: false
    }

    // -----------------------------
    // Pop-out Buttons
    // -----------------------------
    Rectangle {
        id: popLogsButton
        width: 120; height: 32; radius: 6
        color: "#aa55ff"
        anchors.left: settingsButton.left
        anchors.top: settingsButton.bottom
        anchors.topMargin: 90

        Text { anchors.centerIn: parent; text: "Pop-out Logs"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                StateBridge.popLogs()
            }
        }
    }

    Rectangle {
        id: popProfileButton
        width: 120; height: 32; radius: 6
        color: "#55aaff"
        anchors.left: popLogsButton.left
        anchors.top: popLogsButton.bottom
        anchors.topMargin: 10

        Text { anchors.centerIn: parent; text: "Pop-out Profile"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                StateBridge.popProfile()
            }
        }
    }

    Rectangle {
        id: popQuickButton
        width: 120; height: 32; radius: 6
        color: "#ffaa55"
        anchors.left: popProfileButton.left
        anchors.top: popProfileButton.bottom
        anchors.topMargin: 10

        Text { anchors.centerIn: parent; text: "Pop-out Quick"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                StateBridge.popQuick()
            }
        }
    }

    // -----------------------------
    // Plugin Panel Button
    // -----------------------------
    Rectangle {
        id: pluginButton
        width: 100; height: 32; radius: 6
        color: "#cc55aa"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: profileButton.bottom; anchors.topMargin: 50

        Text { anchors.centerIn: parent; text: "Plugins"; color: "white" }

        MouseArea {
            anchors.fill: parent
            onClicked: {
                soundLoader.item.playClick()
                pluginLoader.visible = !pluginLoader.visible
                toastLoader.item.show("Plugins " + (pluginLoader.visible ? "opened" : "closed"))
            }
        }
    }

    Loader {
        id: pluginLoader
        source: "plugin_panel.qml"
        anchors.right: parent.right; anchors.rightMargin: 20
        anchors.top: pluginButton.bottom; anchors.topMargin: 10
        visible: false
    }

    // -----------------------------
    // Toast System
    // -----------------------------
    Loader {
        id: toastLoader
        source: "toast.qml"
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40
    }

    // -----------------------------
    // Auto-Save Timer
    // -----------------------------
    Timer {
        id: autosaveTimer
        interval: 8000
        repeat: true
        running: true
        onTriggered: {
            StateBridge.updateDraft(chatInput.text)
            toastLoader.item.show("Auto-saved")
        }
    }

    // -----------------------------
    // Startup Restore
    // -----------------------------
    Component.onCompleted: {
        settingsLoader.visible = assistant.session_state.panels.settings
        profileLoader.visible = assistant.session_state.panels.profile
        logViewerLoader.visible = assistant.session_state.panels.logs
        quickPanelLoader.visible = assistant.session_state.panels.quick

        chatInput.text = assistant.session_state.draft

        if (assistant.session_state.crashed)
            toastLoader.item.show("Recovered from backup")

        StateBridge.toastRequested.connect(function(msg) {
            toastLoader.item.show(msg)
        })
    }

    // -----------------------------
    // Pop-out Window Creation
    // -----------------------------
    Connections {
        target: StateBridge

        function onOpenLogsWindow() {
            var w = Qt.createComponent("logs_window.qml").createObject(root)
            w.x = assistant.session_state.windows.logs.x
            w.y = assistant.session_state.windows.logs.y
            w.width = assistant.session_state.windows.logs.w
            w.height = assistant.session_state.windows.logs.h

            w.onClosing.connect(function() {
                StateBridge.updateWindowGeometry(
                    "logs", w.x, w.y, w.width, w.height
                )
            })
        }

        function onOpenProfileWindow() {
            var w = Qt.createComponent("profile_window.qml").createObject(root)
            w.x = assistant.session_state.windows.profile.x
            w.y = assistant.session_state.windows.profile.y
            w.width = assistant.session_state.windows.profile.w
            w.height = assistant.session_state.windows.profile.h

            w.onClosing.connect(function() {
                StateBridge.updateWindowGeometry(
                    "profile", w.x, w.y, w.width, w.height
                )
            })
        }

        function onOpenQuickWindow() {
            var w = Qt.createComponent("quick_window.qml").createObject(root)
            w.x = assistant.session_state.windows.quick.x
            w.y = assistant.session_state.windows.quick.y
            w.width = assistant.session_state.windows.quick.w
            w.height = assistant.session_state.windows.quick.h

            w.onClosing.connect(function() {
                StateBridge.updateWindowGeometry(
                    "quick", w.x, w.y, w.width, w.height
                )
            })
        }

        function onPluginExecuted(resultJson) {
            toastLoader.item.show("Plugin executed")
        }
    }

    // -----------------------------
    // Global Hotkeys
    // -----------------------------
    Keys.onPressed: {
        if (event.key === Qt.Key_Space && event.modifiers & Qt.ControlModifier) {
            root.visible = !root.visible
            toastLoader.item.show(root.visible ? "Assistant shown" : "Assistant hidden")
            event.accepted = true
        }

        if (event.key === Qt.Key_M &&
            (event.modifiers & Qt.ControlModifier) &&
            (event.modifiers & Qt.ShiftModifier)) {
            StateBridge.toggleMic()
            event.accepted = true
        }

        if (event.key === Qt.Key_L &&
            (event.modifiers & Qt.ControlModifier) &&
            (event.modifiers & Qt.ShiftModifier)) {
            logViewerLoader.visible = !logViewerLoader.visible
            StateBridge.setLogsOpen(logViewerLoader.visible)
            toastLoader.item.show("Logs " + (logViewerLoader.visible ? "opened" : "closed"))
            event.accepted = true
        }

        if (event.key === Qt.Key_P &&
            (event.modifiers & Qt.ControlModifier) &&
            (event.modifiers & Qt.ShiftModifier)) {
            profileLoader.visible = !profileLoader.visible
            StateBridge.setProfileOpen(profileLoader.visible)
            toastLoader.item.show("Profile " + (profileLoader.visible ? "opened" : "closed"))
            event.accepted = true
        }

        if (event.key === Qt.Key_Q &&
            (event.modifiers & Qt.ControlModifier) &&
            (event.modifiers & Qt.ShiftModifier)) {
            quickPanelLoader.visible = !quickPanelLoader.visible
            StateBridge.setQuickOpen(quickPanelLoader.visible)
            toastLoader.item.show("Quick panel " + (quickPanelLoader.visible ? "opened" : "closed"))
            event.accepted = true
        }
    }
}
