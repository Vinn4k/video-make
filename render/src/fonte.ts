import { loadFont } from "@remotion/google-fonts/Montserrat";

export const { fontFamily } = loadFont("normal", {
  weights: ["600", "800", "900"],
  subsets: ["latin", "latin-ext"],
});
