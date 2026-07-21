import "./chihiros-notification-ui.js?v=0.1.0";
import "./chihiros-led-core-card.js?v=0.2.1147";

class ChihirosLedCorePanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  connectedCallback() {
    this.render();
  }

  render() {
    if (!this._card) {
      this.innerHTML = `
        <style>
          :host {
            display: block;
            min-height: 100vh;
            background: var(--primary-background-color);
            color: var(--primary-text-color);
          }
          .chihiros-panel {
            width: 100%;
            box-sizing: border-box;
            padding: 12px;
          }
        </style>
        <main class="chihiros-panel">
          <chihiros-led-core-card></chihiros-led-core-card>
        </main>`;
      this._card = this.querySelector("chihiros-led-core-card");
      this._card.setConfig({
        default_tab: "led",
        enabled_tabs: ["led", "config"],
        installed_plugins: [],
        addon_mode: true,
        show_mac: true,
        show_fan_demo: true,
      });
    }
    if (this._hass) {
      this._card.hass = this._hass;
    }
  }
}

customElements.define("chihiros-led-core-panel", ChihirosLedCorePanel);
