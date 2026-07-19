import "./chihiros-notification-ui.js?v=0.1.0";
import "./chihiros-doser-card-v3.js?v=0.2.1008";
import "/chihiros_plugin_static/doser/www/doser-plugin.js?v=0.1.67";
import "/chihiros_plugin_static/wireshark/www/wireshark-plugin.js?v=0.1.52";
import "/chihiros_plugin_static/ctl/www/ctl-plugin.js?v=0.1.1";
import "/chihiros_plugin_static/ruehrer/www/ruehrer-plugin.js?v=0.1.9";
import "/chihiros_plugin_static/heizer/www/heizer-plugin.js?v=0.1.9";

window.ChihirosAddonApi = window.ChihirosAddonApi || {
  callPluginBackend: async (plugin, functionName, args = []) => {
    const response = await fetch("/api/chihiros/plugin-backend", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ plugin, function: functionName, args }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || data.output || "Plugin Aktion fehlgeschlagen");
    return data;
  },
};

class ChihirosPanel extends HTMLElement {
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
          <chihiros-doser-card-v3></chihiros-doser-card-v3>
        </main>`;
      this._card = this.querySelector("chihiros-doser-card-v3");
      this._card.setConfig({
        default_tab: "led",
        enabled_tabs: ["led", "doser", "ruehrer", "heizer", "wireshark", "ctl", "config"],
        installed_plugins: ["doser", "ruehrer", "heizer", "wireshark", "ctl"],
        addon_mode: true,
        show_mac: true,
      });
    }
    if (this._hass) {
      this._card.hass = this._hass;
    }
  }
}

customElements.define("chihiros-panel", ChihirosPanel);
