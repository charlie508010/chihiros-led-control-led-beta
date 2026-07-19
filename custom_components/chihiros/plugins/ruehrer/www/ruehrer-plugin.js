window.ChihirosPlugins = window.ChihirosPlugins || {};

window.ChihirosPlugins.ruehrer = {
  id: "ruehrer",
  title: "Ruehrer",
  tabs: ["ruehrer"],
  version: "0.1.9",
  renderPanel(card) {
    return card.haDevicePanel("ruehrer", this.title);
  },
};
