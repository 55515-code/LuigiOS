import QtQuick 2.15;
import calamares.slideshow 1.0;

Presentation {
    id: presentation

    Slide {
        anchors.fill: parent
        Rectangle {
            anchors.fill: parent
            color: "#111713"
            Column {
                anchors.centerIn: parent
                spacing: 18
                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    source: "logo.png"
                    width: 128
                    height: 128
                    fillMode: Image.PreserveAspectFit
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "A focused COSMIC developer workstation"
                    color: "#E8F2EA"
                    font.pixelSize: 24
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "CachyOS performance • reproducible inputs • decentralized delivery"
                    color: "#91A897"
                    font.pixelSize: 16
                }
            }
        }
    }

    function onActivate() {}
    function onLeave() {}
}
