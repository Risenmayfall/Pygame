"""
Pygame - Class'lı Dövüş Oyunu (UI + Mouse Seçim + Animasyon)

GEREKSİNİMLER:
- pygame
- pillow (GIF arkaplanı frame frame oynatmak için)
- pip install pygame pillow -> YÜKLENMESİ GEREKEN

DOSYALAR (aynı klasörde olmalı):
- background.gif
- ares.png
- archer.png
- magician.png
- minotaur.png
"""

import math
import sys
from dataclasses import dataclass

import pygame
from PIL import Image, ImageSequence


# ------------------------------------------------------------
# 1) OYUN MANTIĞI (CLASS YAPISI)
# ------------------------------------------------------------

class Karakter:
    """
    Temel karakter sınıfı.
    isim, can, guc, kalkan değerlerini taşır.
    """
    def __init__(self, isim: str, can: int, guc: int, kalkan: int):
        self.isim = isim
        self.can = can
        self.guc = guc
        self.kalkan = kalkan

    def hayatta_mi(self) -> bool:
        return self.can > 0

    def _hasar_hesapla(self, ham_hasar: float) -> int:
        """
        Kalkanı düşerek hasarı hesaplar.
        Negatif olmasın diye 0'a kırpar.
        """
        net = int(max(0, ham_hasar - self.kalkan))
        return net

    def saldir(self, dusman: "Karakter") -> int:
        """
        Temel saldırı: guc - dusman_kalkan gibi düşünebilirsin.
        Burada net hasar hesaplamasını _hasar_hesapla yapıyor.
        """
        net_hasar = self._hasar_hesapla(self.guc)
        dusman.can -= net_hasar
        dusman.can = max(0, dusman.can)
        return net_hasar


class Magician(Karakter):
    def ates_topu(self, dusman: Karakter) -> int:
        # Özel saldırı: daha yüksek çarpan
        ham = self.guc * 2.0
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net

    def buz_mizrak(self, dusman: Karakter) -> int:
        # Özel saldırı 2: orta-yüksek
        ham = self.guc * 1.6
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net


class Knight(Karakter):
    def samuray_sarkisi(self, dusman: Karakter) -> int:
        ham = self.guc * 1.5
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net

    def kalkan_darbesi(self, dusman: Karakter) -> int:
        ham = self.guc * 1.2
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net


class Tank(Karakter):
    def hucum_vurusu(self, dusman: Karakter) -> int:
        # Tank daha az vurur ama dayanıklıdır
        ham = self.guc * 1.0
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net

    def ezici_slam(self, dusman: Karakter) -> int:
        ham = self.guc * 1.3
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net


class Archer(Karakter):
    def ok_firtinasi(self, dusman: Karakter) -> int:
        ham = self.guc * 1.7
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net

    def keskin_atis(self, dusman: Karakter) -> int:
        ham = self.guc * 2.2
        net = self._hasar_hesapla(ham)
        dusman.can = max(0, dusman.can - net)
        return net


# ------------------------------------------------------------
# 2) GÖRSEL KATMAN (SPRITE BENZERİ WRAPPER)
# ------------------------------------------------------------

@dataclass
class FighterView:
    """
    Bir Karakter'in ekrandaki temsili:
    - karakter: oyun mantığı objesi
    - image: 128px görsel
    - pos: ekrandaki merkez konum
    """
    karakter: Karakter
    image: pygame.Surface
    pos: pygame.Vector2
    alive: bool = True

    @property
    def rect(self) -> pygame.Rect:
        r = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        return r

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, highlight: bool = False, scale: float = 1.0):
        """
        Karakteri ekrana çizer.
        - highlight=True ise etrafına çerçeve atar
        - scale ile büyütüp küçültebiliriz (hedef seçerken büyütme gibi)
        """
        if not self.alive:
            return

        img = self.image
        if abs(scale - 1.0) > 1e-3:
            w, h = img.get_size()
            img = pygame.transform.smoothscale(img, (int(w * scale), int(h * scale)))

        draw_rect = img.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        screen.blit(img, draw_rect)

        # Çerçeve: hedef/aktif seçim için görsel ipucu
        if highlight:
            pygame.draw.rect(screen, (255, 215, 0), draw_rect.inflate(6, 6), 3)

        # İsim ve can bilgisini karakterin altına yaz
        info = f"{self.karakter.isim} | CAN: {self.karakter.can}"
        text = font.render(info, True, (255, 255, 255))
        text_rect = text.get_rect(midtop=(draw_rect.centerx, draw_rect.bottom + 6))
        screen.blit(text, text_rect)

    def hit_test(self, mouse_pos) -> bool:
        """Fare tıklaması bu karakterin üzerine geldi mi?"""
        if not self.alive:
            return False
        return self.rect.collidepoint(mouse_pos)


# ------------------------------------------------------------
# 3) GIF ARKAPLAN (PIL ile frame yükleme)
# ------------------------------------------------------------

class GifBackground:
    """
    background.gif’i açar, frame’leri pygame surface’ine çevirir,
    belli FPS ile oynatır.
    """
    def __init__(self, path: str, target_size: tuple[int, int], fps: int = 12):
        self.frames: list[pygame.Surface] = []
        self.fps = fps
        self.time_acc = 0.0
        self.index = 0

        # GIF'i PIL ile açıyoruz (pygame tek başına GIF animasyonunu oynatmaz)
        pil_img = Image.open(path)

        for frame in ImageSequence.Iterator(pil_img):
            # RGBA'ya çevirip hedef boyuta ölçekle
            fr = frame.convert("RGBA")
            fr = fr.resize(target_size, Image.Resampling.NEAREST)

            # PIL -> pygame Surface
            mode = fr.mode
            data = fr.tobytes()
            surf = pygame.image.frombuffer(data, fr.size, mode).convert_alpha()
            self.frames.append(surf)

        if not self.frames:
            raise RuntimeError("GIF frame bulunamadı.")

    def update(self, dt: float):
        """dt: saniye cinsinden delta time"""
        if len(self.frames) <= 1:
            return
        self.time_acc += dt
        frame_time = 1.0 / self.fps
        while self.time_acc >= frame_time:
            self.time_acc -= frame_time
            self.index = (self.index + 1) % len(self.frames)

    def draw(self, screen: pygame.Surface):
        screen.blit(self.frames[self.index], (0, 0))


# ------------------------------------------------------------
# 4) OYUN DURUMLARI (STATE MACHINE)
# ------------------------------------------------------------

class GameState:
    SELECT_ATTACKER = "SELECT_ATTACKER"
    SELECT_TARGET   = "SELECT_TARGET"
    ATTACK_ANIM     = "ATTACK_ANIM"


class BattleGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Class'lı Dövüş Oyunu - UI + Seçim + Animasyon")

        # Pencere boyutu (arka planı da buna göre ölçekleyeceğiz)
        self.W, self.H = 1200, 675
        self.screen = pygame.display.set_mode((self.W, self.H))
        self.clock = pygame.time.Clock()

        # Fontlar
        self.font_ui = pygame.font.SysFont("arial", 28, bold=True)
        self.font_small = pygame.font.SysFont("arial", 18)

        # Arkaplan GIF
        self.bg = GifBackground("background.gif", (self.W, self.H), fps=12)

        # Log paneli (son saldırı sonuçlarını yazmak için)
        self.logs: list[str] = []

        # Karakter görselleri
        self.img_ares = pygame.image.load("ares.png").convert_alpha()
        self.img_archer = pygame.image.load("archer.png").convert_alpha()
        self.img_magician = pygame.image.load("magician.png").convert_alpha()
        self.img_minotaur = pygame.image.load("minotaur.png").convert_alpha()

        # Sınıfları oluşturalım (eski projedeki mantığa benzer)
        # Not: isimleri öğrencilerin daha “oyunsu” seveceği gibi verdim :)
        self.fighters: list[FighterView] = [
            FighterView(Knight("Ares Şövalyesi", 100, 20, 10), self.img_ares, pygame.Vector2(250, 250)),
            FighterView(Archer("Elf Okçusu", 70, 28, 4), self.img_archer, pygame.Vector2(450, 420)),
            FighterView(Magician("Karanlık Büyücü", 85, 24, 6), self.img_magician, pygame.Vector2(750, 250)),
            FighterView(Tank("Minotor Tank", 140, 16, 12), self.img_minotaur, pygame.Vector2(950, 420)),
        ]

        # UI akışı için state
        self.state = GameState.SELECT_ATTACKER
        self.selected_attacker: FighterView | None = None
        self.selected_target: FighterView | None = None

        # Animasyon parametreleri
        self.anim_t = 0.0                # 0 -> 1 arası ilerleme
        self.anim_duration = 0.75        # saldırı anim süresi (saniye)
        self.attacker_start_pos = pygame.Vector2(0, 0)

        # Başlangıç mesajı
        self.push_log("SAVAŞ BAŞLIYOR! Önce saldıracak kişiyi seç.")

    # ----------------- yardımcılar -----------------

    def push_log(self, msg: str):
        """Log listesine mesaj ekler, uzunluğu sınırlı tutar."""
        self.logs.append(msg)
        if len(self.logs) > 8:
            self.logs.pop(0)

    def alive_fighters(self) -> list[FighterView]:
        return [f for f in self.fighters if f.alive and f.karakter.hayatta_mi()]

    def cleanup_dead(self):
        """Canı 0 olanları sahneden kaldır."""
        for f in self.fighters:
            if f.alive and not f.karakter.hayatta_mi():
                f.alive = False
                self.push_log(f"💀 {f.karakter.isim} haritadan silindi!")

                # Eğer seçiliyse seçimleri sıfırla
                if self.selected_attacker is f:
                    self.selected_attacker = None
                if self.selected_target is f:
                    self.selected_target = None

    def any_game_over(self) -> bool:
        """Tek kişi kaldıysa oyun bitti diyebiliriz."""
        return len(self.alive_fighters()) <= 1

    # ----------------- saldırı seçimi -----------------

    def perform_attack(self, attacker: Karakter, target: Karakter) -> tuple[str, int]:
        """
        Saldırıyı attacker'ın classına göre seçip uygular.
        Geriye (saldırı_adı, hasar) döndürür.
        """
        # Burada istersen “rastgele özel saldırı” da yapabilirsin.
        # Şimdilik basit: her class’ın 1 özel saldırısını kullanalım.
        if isinstance(attacker, Magician):
            dmg = attacker.ates_topu(target)
            return ("Ateş Topu", dmg)

        if isinstance(attacker, Knight):
            dmg = attacker.samuray_sarkisi(target)
            return ("Samuray Şarkısı", dmg)

        if isinstance(attacker, Tank):
            dmg = attacker.ezici_slam(target)
            return ("Ezici Slam", dmg)

        if isinstance(attacker, Archer):
            dmg = attacker.keskin_atis(target)
            return ("Keskin Atış", dmg)

        # Fallback (normal saldırı)
        dmg = attacker.saldir(target)
        return ("Temel Saldırı", dmg)

    # ----------------- event handling -----------------

    def handle_click_select_attacker(self, mouse_pos):
        """State: SELECT_ATTACKER -> saldıracak karakteri seç"""
        for f in self.alive_fighters():
            if f.hit_test(mouse_pos):
                self.selected_attacker = f
                self.state = GameState.SELECT_TARGET
                self.push_log(f"⚔️ Saldıracak: {f.karakter.isim}")
                self.push_log("Şimdi hedefi seç: Kime saldırılacak?")
                return

    def handle_click_select_target(self, mouse_pos):
        """State: SELECT_TARGET -> hedef seç"""
        if not self.selected_attacker or not self.selected_attacker.alive:
            # saldıran yoksa geri dön
            self.state = GameState.SELECT_ATTACKER
            self.push_log("Saldıracak kişiyi seç (tekrar).")
            return

        for f in self.alive_fighters():
            if f is self.selected_attacker:
                continue
            if f.hit_test(mouse_pos):
                self.selected_target = f
                self.start_attack_anim()
                return

    def start_attack_anim(self):
        """Saldırı animasyonunu başlatır."""
        self.state = GameState.ATTACK_ANIM
        self.anim_t = 0.0
        self.attacker_start_pos = self.selected_attacker.pos.copy()
        self.push_log(f"🎯 Hedef: {self.selected_target.karakter.isim}")

    # ----------------- update loop -----------------

    def update_attack_anim(self, dt: float):
        """
        Saldıran karakter hedefe gidip geri gelir.
        t: 0->1
        0->0.5 yaklaşma, 0.5->1 geri dönüş
        Darbe anı: t ~ 0.5 civarı
        """
        if not self.selected_attacker or not self.selected_target:
            self.state = GameState.SELECT_ATTACKER
            return

        self.anim_t += dt / self.anim_duration
        t = min(self.anim_t, 1.0)

        start = self.attacker_start_pos
        target_pos = self.selected_target.pos

        # “Gidip gelme” için iki fazlı lerp
        if t <= 0.5:
            # hedefe yaklaş
            k = t / 0.5
            pos = start.lerp(target_pos, k)
        else:
            # geri dön
            k = (t - 0.5) / 0.5
            pos = target_pos.lerp(start, k)

        self.selected_attacker.pos = pos

        # Darbe anı: t ilk kez 0.5'i geçtiğinde hasarı uygula
        # Bunu basit bir eşikle kontrol edelim:
        if 0.48 < t < 0.52 and not hasattr(self, "_damage_applied"):
            self._damage_applied = True

            attack_name, dmg = self.perform_attack(
                self.selected_attacker.karakter,
                self.selected_target.karakter
            )
            self.push_log(f"💥 {self.selected_attacker.karakter.isim} -> {attack_name} ({dmg} hasar)")
            self.push_log(f"   {self.selected_target.karakter.isim} kalan can: {self.selected_target.karakter.can}")

            self.cleanup_dead()

        # Anim bitti: pozisyonu sıfırla, seçimleri temizle, tekrar seçim moduna dön
        if t >= 1.0:
            # attacker pozisyonu garanti yerine otursun
            self.selected_attacker.pos = self.attacker_start_pos

            # Darbe flag'ini kaldır
            if hasattr(self, "_damage_applied"):
                delattr(self, "_damage_applied")

            # Oyun bitti mi?
            if self.any_game_over():
                survivors = self.alive_fighters()
                if survivors:
                    self.push_log(f"🏆 KAZANAN: {survivors[0].karakter.isim}")
                else:
                    self.push_log("😵 Herkes düştü. Bu… garip bir evren.")
                # Oyun bittiğinde seçimleri durdurup aynı ekranda bırakıyoruz.
                self.state = GameState.ATTACK_ANIM
                return

            # Yeni tur
            self.selected_attacker = None
            self.selected_target = None
            self.state = GameState.SELECT_ATTACKER
            self.push_log("Yeni tur: Saldıracak kişiyi seç.")

    # ----------------- drawing -----------------

    def draw_ui_panel(self):
        """
        Üstte UI yönergeleri, altta log paneli.
        """
        # Üst bar (yarı saydam bir şerit)
        bar = pygame.Surface((self.W, 60), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 140))
        self.screen.blit(bar, (0, 0))

        # State'e göre ana yönerge
        if self.state == GameState.SELECT_ATTACKER:
            title = "Saldıracak kişiyi seç"
        elif self.state == GameState.SELECT_TARGET:
            title = "Kime saldırılacak? (Hedefi tıkla)"
        else:
            title = "Saldırı gerçekleşiyor..."

        text = self.font_ui.render(title, True, (255, 255, 255))
        self.screen.blit(text, (20, 15))

        # Log panel (alt)
        log_h = 160
        log_panel = pygame.Surface((self.W, log_h), pygame.SRCALPHA)
        log_panel.fill((0, 0, 0, 160))
        self.screen.blit(log_panel, (0, self.H - log_h))

        y = self.H - log_h + 12
        for line in self.logs:
            t = self.font_small.render(line, True, (230, 230, 230))
            self.screen.blit(t, (18, y))
            y += 18

    def draw_fighters(self):
        """
        Karakterleri çizer:
        - saldıran seçiliyse highlight
        - hedef seçme modunda hedefler büyür + highlight
        """
        for f in self.fighters:
            if not f.alive:
                continue

            highlight = False
            scale = 1.0

            # Saldıran seçildi mi?
            if self.selected_attacker is f:
                highlight = True

            # Hedef seçme aşamasında hedefler büyüsün
            if self.state == GameState.SELECT_TARGET and self.selected_attacker is not None:
                if f is not self.selected_attacker:
                    # hedef seçilebilir karakterler büyür
                    scale = 1.25

            # Seçili hedef varsa ekstra vurgula
            if self.selected_target is f:
                highlight = True
                scale = 1.35

            f.draw(self.screen, self.font_small, highlight=highlight, scale=scale)

    # ----------------- main loop -----------------

    def run(self):
        while True:
            dt = self.clock.tick(60) / 1000.0  # saniye
            self.bg.update(dt)

            # Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()

                    # Oyun bittiyse tıklamaları kilitle
                    if self.any_game_over():
                        continue

                    if self.state == GameState.SELECT_ATTACKER:
                        self.handle_click_select_attacker(mouse_pos)
                    elif self.state == GameState.SELECT_TARGET:
                        self.handle_click_select_target(mouse_pos)

            # Update
            if self.state == GameState.ATTACK_ANIM and not self.any_game_over():
                self.update_attack_anim(dt)

            # Draw
            self.bg.draw(self.screen)
            self.draw_fighters()
            self.draw_ui_panel()

            pygame.display.flip()


if __name__ == "__main__":
    BattleGame().run()
