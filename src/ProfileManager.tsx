/**
 * Saved profiles UI.
 *
 * Lets the user name + save the current effect, then switch between
 * named snapshots. Profiles are stored in the backend's config.json.
 */
import {
  ButtonItem,
  ConfirmModal,
  DialogButton,
  Dropdown,
  DropdownOption,
  PanelSection,
  PanelSectionRow,
  showModal,
  TextField,
} from "@decky/ui";
import React, { useCallback, useEffect, useState } from "react";

import {
  deleteProfile,
  listProfiles,
  loadProfile,
  saveProfile,
  type ProfileEntry,
} from "./api";

interface Props {
  onLoad: () => void; // called after a profile is loaded so parent re-fetches status
}

export default function ProfileManager({ onLoad }: Props) {
  const [profiles, setProfiles] = useState<ProfileEntry[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [newName, setNewName] = useState("");

  const refresh = useCallback(async () => {
    const list = await listProfiles();
    setProfiles(list ?? []);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const options: DropdownOption[] = profiles.map((p) => ({
    data: p.name,
    label: `${p.name} (${p.effect})`,
  }));

  async function handleSave() {
    const name = newName.trim();
    if (!name) return;
    await saveProfile(name);
    setNewName("");
    refresh();
  }

  async function handleLoad() {
    if (!selected) return;
    await loadProfile(selected);
    onLoad();
  }

  async function handleDelete() {
    if (!selected) return;
    showModal(
      <ConfirmModal
        strTitle="Delete profile"
        strDescription={`Delete "${selected}"?`}
        strOKButtonText="Delete"
        onOK={async () => {
          await deleteProfile(selected);
          setSelected("");
          refresh();
        }}
      />
    );
  }

  return (
    <PanelSection title="Profiles">
      <PanelSectionRow>
        <TextField
          label="Profile name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="e.g. Gaming, Movie mode"
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={handleSave}
          disabled={!newName.trim()}
        >
          Save current as profile
        </ButtonItem>
      </PanelSectionRow>

      {profiles.length > 0 && (
        <>
          <PanelSectionRow>
            <Dropdown
              label="Load profile"
              rgOptions={options}
              selectedOption={selected}
              onChange={(opt) => setSelected(opt.data as string)}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ display: "flex", gap: 8 }}>
              <DialogButton
                onClick={handleLoad}
                disabled={!selected}
                style={{ flexGrow: 1 }}
              >
                Load
              </DialogButton>
              <DialogButton
                onClick={handleDelete}
                disabled={!selected}
                style={{ flexGrow: 1 }}
              >
                Delete
              </DialogButton>
            </div>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
}
