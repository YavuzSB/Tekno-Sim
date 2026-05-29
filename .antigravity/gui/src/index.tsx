import { ExtensionContext } from "@foxglove/studio-extension-types";
import { Panel } from "./Panel";

export function activate(context: ExtensionContext): void {
  context.registerPanel({ name: "TeknoSim Control Panel", component: Panel });
}
