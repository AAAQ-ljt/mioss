import { BrowserRouter, Route, Routes } from "react-router-dom";
import StudioLayout from "./layout/StudioLayout";
import PresetsPage from "./pages/PresetsPage";
import PromptLibraryPage from "./pages/PromptLibraryPage";
import RelayPage from "./pages/RelayPage";
import StoryPage from "./pages/StoryPage";
import StoryboardPage from "./pages/StoryboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<StudioLayout />}>
          <Route path="/" element={<PromptLibraryPage />} />
          <Route path="/relay" element={<RelayPage />} />
          <Route path="/presets" element={<PresetsPage />} />
          <Route path="/story" element={<StoryPage />} />
          <Route path="/board" element={<StoryboardPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
