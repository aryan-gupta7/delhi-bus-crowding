import { useState } from "react";
import { ScrollView, TextInput, View } from "react-native";
import type { DayType } from "../api/types";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { LevelPill } from "../components/LevelPill";
import { ScreenHeader } from "../components/ScreenHeader";
import { Segmented } from "../components/Segmented";
import { Text } from "../components/Text";
import type { Lang } from "../i18n/i18n";
import { useApp } from "../state/AppState";
import { useTheme, type ThemeMode } from "../theme/ThemeProvider";
import { font, radius, TOUCH } from "../theme/tokens";

export function AboutScreen() {
  const { t, lang, setLang, theme, setTheme, baseUrl, setBaseUrl } = useApp();
  const { palette } = useTheme();
  const [day, setDay] = useState<DayType>("weekday");
  const [url, setUrl] = useState(baseUrl);
  const [saved, setSaved] = useState(false);

  return (
    <View style={{ flex: 1 }}>
      <ScreenHeader title={t("aboutTitle")} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 14 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>{([1, 2, 3, 0] as const).map((c) => <LevelPill key={c} level={c} size="sm" />)}</View>
        <Text>{t("aboutLevels")}</Text>
        <Text tone="sec" size={14}>{t("aboutEvidence")}</Text>
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
          <LevelPill level={2} tier="High" size="sm" /><LevelPill level={2} tier="Medium" size="sm" /><LevelPill level={2} tier="Low" size="sm" />
        </View>
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}><Badge kind="leans" label={t("leans")} /><Text tone="sec" size={13} style={{ flex: 1 }}>{t("aboutLeans")}</Text></View>
          <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}><Badge label={t("firm")} /><Text tone="sec" size={13} style={{ flex: 1 }}>{t("firmTip")}</Text></View>
        </View>

        <Card style={{ gap: 10 }}>
          <Text medium size={14} tone="sec">{t("whichDay")}</Text>
          <Segmented<DayType> options={[{ key: "weekday", label: t("weekday") }, { key: "weekend", label: t("weekend") }]} value={day} onChange={setDay} />
          <Text tone="sec" size={14}>{t(day === "weekend" ? "basisWeekend" : "basisWeekday")}</Text>
          {day === "weekend" ? <Text tone="mut" size={13}>{t("roughWeekend")}</Text> : null}
        </Card>

        <Text tone="sec" size={14}>{t("aboutNot")}</Text>
        <Text tone="mut" size={13}>{t("sample")}</Text>

        <Card style={{ gap: 10 }}>
          <Text medium size={14} tone="sec">{t("settings")}</Text>
          <Text size={13} tone="mut">{t("theme")}</Text>
          <Segmented<ThemeMode> options={[{ key: "auto", label: t("themeAuto") }, { key: "light", label: t("themeLight") }, { key: "dark", label: t("themeDark") }]} value={theme} onChange={setTheme} />
          <Text size={13} tone="mut">{t("language")}</Text>
          <Segmented<Lang> options={[{ key: "en", label: "English" }, { key: "hi", label: "हिन्दी" }]} value={lang} onChange={setLang} />
          {lang === "hi" ? <Text tone="mut" size={12}>{t("aboutHindi")}</Text> : null}
          <Text size={13} tone="mut">{t("server")}</Text>
          <TextInput value={url} onChangeText={(v) => { setUrl(v); setSaved(false); }} autoCapitalize="none" autoCorrect={false} keyboardType="url" accessibilityLabel={t("server")}
            style={{ minHeight: TOUCH, paddingHorizontal: 12, color: palette.ink, fontFamily: font.regular, fontSize: 15, borderRadius: radius.control, borderWidth: 1, borderColor: palette.border }} />
          <Text tone="mut" size={12}>{t("serverHint")}</Text>
          <Button kind="quiet" label={saved ? t("saved") : t("save")} onPress={() => { setBaseUrl(url.trim()); setSaved(true); }} style={{ alignSelf: "flex-start", paddingHorizontal: 0 }} />
        </Card>
      </ScrollView>
    </View>
  );
}
