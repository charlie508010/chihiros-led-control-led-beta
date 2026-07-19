window.ChihirosPlugins = window.ChihirosPlugins || {};

window.ChihirosPlugins.heizer = {
  id: "heizer",
  title: "Heizer",
  tabs: ["heizer"],
  version: "0.1.9",
  renderPanel(card) {
    return card.haDevicePanel("heizer", this.title);
  },
};
