import json
import random
import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import openai

from astrbot.api import AstrBotConfig
from astrbot.api.event import filter
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register

logger = logging.getLogger("astrbot_plugin_lifesim")

WORLDS = {
    "武侠江湖": {
        "desc": "刀光剑影的江湖世界，以武为尊，门派林立",
        "start": "你出生在一个动荡的武林世家，父亲曾是赫赫有名的剑客"
    },
    "都市白领": {
        "desc": "现代都市的职场风云，从小职员到人生巅峰",
        "start": "你出生在一个普通的城市家庭，父母都是工薪阶层"
    },
    "仙侠修真": {
        "desc": "修仙问道的奇幻世界，追求长生不老",
        "start": "你出生在修仙界的一个小村庄，天生灵根觉醒"
    },
    "末日生存": {
        "desc": "文明崩塌后的废土世界，为了生存而战",
        "start": "你出生在末日后的避难所，资源匮乏，危机四伏"
    },
    "古代宫廷": {
        "desc": "波谲云诡的宫廷世界，权力与阴谋交织",
        "start": "你出生在皇城根下的一个官宦之家"
    },
    "奇幻冒险": {
        "desc": "充满魔法与怪物的奇幻大陆，勇者的传说",
        "start": "你出生在一个宁静的小村庄，村外就是充满危险的黑暗森林"
    },
    "赛博朋克": {
        "desc": "高科技低生活的未来都市，霓虹灯下的暗影",
        "start": "你出生在城市的底层区域，被电子垃圾和霓虹灯包围"
    },
    "海岛求生": {
        "desc": "流落荒岛的原始生存，从零开始建设文明",
        "start": "你在一次海难后醒来，发现自己被困在一个未知的热带岛屿上"
    }
}

IMPORTANT_EVENTS = [
    {"title": "天赋觉醒", "desc": "你展现出异于常人的天赋，让周围的人大为惊讶。", "age_range": (1, 12)},
    {"title": "童年危机", "desc": "一场突如其来的变故打破了你的平静生活。", "age_range": (1, 12)},
    {"title": "贵人相助", "desc": "一位神秘人物出现在你的生命中，给予了你重要的指引。", "age_range": (5, 22)},
    {"title": "少年磨难", "desc": "你遭遇了人生中的第一次重大挫折。", "age_range": (13, 22)},
    {"title": "命运转折", "desc": "一个意外的机会出现在你面前。", "age_range": (13, 40)},
    {"title": "情感风暴", "desc": "你经历了一段深刻的感情，内心波澜起伏。", "age_range": (16, 40)},
    {"title": "事业起步", "desc": "你在事业上迈出了关键的一步。", "age_range": (20, 40)},
    {"title": "重大抉择", "desc": "你面临人生中一个重要的十字路口，方向不同，命运迥异。", "age_range": (20, 50)},
    {"title": "危机降临", "desc": "一场危机考验着你的能力和品格。", "age_range": (20, 60)},
    {"title": "中年觉醒", "desc": "你对人生有了新的认识和感悟，需要做出改变。", "age_range": (35, 60)},
    {"title": "命运再次考验", "desc": "你再次面临重大考验，这次的选择将决定你晚年的走向。", "age_range": (40, 70)},
    {"title": "人生巅峰", "desc": "你达到了人生的一个高峰，前方是更广阔的天地还是万丈深渊？", "age_range": (30, 65)},
    {"title": "传承之责", "desc": "你开始思考如何将自己的经验和智慧传承下去。", "age_range": (50, 80)},
    {"title": "暮年危机", "desc": "你面临最后的重大考验，生命的意义在此刻浮现。", "age_range": (60, 100)},
    {"title": "人生终章", "desc": "你感受到了生命的召唤，这是最后的时刻。", "age_range": (70, 120)},
]

TALENTS = [
    {"name": "天生神力", "desc": "力量+3", "bonus": {"strength": 3}, "rarity": 5},
    {"name": "过目不忘", "desc": "智力+3", "bonus": {"intelligence": 3}, "rarity": 5},
    {"name": "魅力四射", "desc": "魅力+3", "bonus": {"charisma": 3}, "rarity": 5},
    {"name": "天选之人", "desc": "运气+3", "bonus": {"luck": 3}, "rarity": 5},
    {"name": "全能天才", "desc": "全属性+1", "bonus": {"strength": 1, "intelligence": 1, "charisma": 1, "luck": 1}, "rarity": 1},
    {"name": "身强体壮", "desc": "力量+2 寿命+5", "bonus": {"strength": 2, "max_age": 5}, "rarity": 8},
    {"name": "聪明伶俐", "desc": "智力+2", "bonus": {"intelligence": 2}, "rarity": 8},
    {"name": "能说会道", "desc": "魅力+2", "bonus": {"charisma": 2}, "rarity": 8},
    {"name": "福星高照", "desc": "运气+2 寿命+3", "bonus": {"luck": 2, "max_age": 3}, "rarity": 8},
    {"name": "逆境重生", "desc": "全属性+2", "bonus": {"strength": 2, "intelligence": 2, "charisma": 2, "luck": 2}, "rarity": 2},
    {"name": "天妒英才", "desc": "全属性+4 寿命-20", "bonus": {"strength": 4, "intelligence": 4, "charisma": 4, "luck": 4, "max_age": -20}, "rarity": 1},
    {"name": "大器晚成", "desc": "40岁后属性翻倍", "bonus": {"late_bloomer": 1}, "rarity": 3},
    {"name": "早慧", "desc": "16岁前成长速度+50%", "bonus": {"early_growth": 50}, "rarity": 6},
    {"name": "乐观开朗", "desc": "运气+1 魅力+1", "bonus": {"luck": 1, "charisma": 1}, "rarity": 10},
    {"name": "沉默寡言", "desc": "智力+2 魅力-1", "bonus": {"intelligence": 2, "charisma": -1}, "rarity": 10},
    {"name": "体弱多病", "desc": "力量-1 智力+3", "bonus": {"strength": -1, "intelligence": 3}, "rarity": 7},
    {"name": "命途多舛", "desc": "运气-2 全属性+1", "bonus": {"luck": -2, "strength": 1, "intelligence": 1, "charisma": 1}, "rarity": 7},
    {"name": "平平无奇", "desc": "没有天赋也是一种天赋", "bonus": {}, "rarity": 15},
    {"name": "天生领袖", "desc": "魅力+2 力量+1", "bonus": {"charisma": 2, "strength": 1}, "rarity": 6},
    {"name": "好奇宝宝", "desc": "智力+1 运气+1", "bonus": {"intelligence": 1, "luck": 1}, "rarity": 8},
    {"name": "铁血战士", "desc": "力量+2 魅力-1", "bonus": {"strength": 2, "charisma": -1}, "rarity": 7},
    {"name": "医者仁心", "desc": "智力+1 魅力+2", "bonus": {"intelligence": 1, "charisma": 2}, "rarity": 7},
    {"name": "赌徒命格", "desc": "运气+3 力量-1", "bonus": {"luck": 3, "strength": -1}, "rarity": 5},
    {"name": "学者之魂", "desc": "智力+2 运气-1", "bonus": {"intelligence": 2, "luck": -1}, "rarity": 8},
    {"name": "浪子回头", "desc": "全属性+1 寿命+10", "bonus": {"strength": 1, "intelligence": 1, "charisma": 1, "luck": 1, "max_age": 10}, "rarity": 2},
    {"name": "苦行僧", "desc": "力量+2 智力+2 魅力-2", "bonus": {"strength": 2, "intelligence": 2, "charisma": -2}, "rarity": 5},
    {"name": "艺术家", "desc": "魅力+2 智力+1", "bonus": {"charisma": 2, "intelligence": 1}, "rarity": 7},
    {"name": "冒险家", "desc": "力量+1 运气+2", "bonus": {"strength": 1, "luck": 2}, "rarity": 6},
    {"name": "谋略家", "desc": "智力+2 魅力+1", "bonus": {"intelligence": 2, "charisma": 1}, "rarity": 6},
    {"name": "天煞孤星", "desc": "力量+3 魅力-2 运气+2", "bonus": {"strength": 3, "charisma": -2, "luck": 2}, "rarity": 3},
]

IDENTITY = [
    {"name": "富家子弟", "desc": "出生富裕家庭，资源丰富", "bonus": {"luck": 2, "charisma": 1}},
    {"name": "寒门学子", "desc": "出身贫寒，但志向远大", "bonus": {"intelligence": 2, "strength": 1}},
    {"name": "将门之后", "desc": "军人家庭，从小习武", "bonus": {"strength": 3}},
    {"name": "医者传人", "desc": "医学世家，精通药理", "bonus": {"intelligence": 2, "luck": 1}},
    {"name": "商贾之子", "desc": "商人家庭，耳濡目染", "bonus": {"charisma": 2, "luck": 1}},
    {"name": "书香门第", "desc": "文化世家，诗书传家", "bonus": {"intelligence": 3}},
    {"name": "江湖艺人", "desc": "漂泊四方的艺人家庭", "bonus": {"charisma": 2, "luck": 1}},
    {"name": "孤儿", "desc": "无依无靠，独自成长", "bonus": {"strength": 1, "intelligence": 1, "luck": 1}}
]


def calc_max_age(strength: int, luck: int, talent_bonus: int = 0) -> int:
    base = 75
    s_bonus = (strength - 5) * 2
    l_bonus = (luck - 5) * 1
    rand = random.randint(-5, 5)
    return max(40, min(120, base + s_bonus + l_bonus + rand + talent_bonus))


def calc_death_chance(age: int, max_age: int, luck: int, strength: int) -> float:
    death_chance = 0.0
    if age < 5:
        death_chance = 0.08
    elif age > max_age:
        over = age - max_age
        death_chance = min(0.95, 0.3 + over * 0.15)
    elif age > max_age - 10:
        near = age - (max_age - 10)
        death_chance = min(0.80, 0.05 + near * 0.08)
    elif age > 60:
        death_chance = 0.02
    elif age > 50:
        death_chance = 0.01
    else:
        death_chance = 0.005
    luck_bonus = max(-0.5, min(0.5, (5 - luck) * 0.02))
    strength_bonus = max(-0.3, min(0.3, (3 - strength) * 0.015))
    death_chance += luck_bonus + strength_bonus
    death_chance = max(0.0, min(0.95, death_chance))
    return death_chance


def calc_score(attrs: dict, talents: list, important_choices: list, alive_years: int) -> dict:
    total_attrs = sum(attrs.values())
    talent_score = len(talents) * 5
    choice_score = len(important_choices) * 3
    year_score = alive_years * 0.5
    total = total_attrs + talent_score + choice_score + year_score
    grade = "F"
    if total >= 150: grade = "SSS"
    elif total >= 120: grade = "SS"
    elif total >= 90: grade = "S"
    elif total >= 70: grade = "A"
    elif total >= 50: grade = "B"
    elif total >= 35: grade = "C"
    elif total >= 20: grade = "D"
    return {"total": round(total), "grade": grade, "talent_score": talent_score, "choice_score": choice_score, "year_score": round(year_score, 1)}


def get_life_comment(grade: str, attrs: dict, alive_years: int) -> str:
    comments = {
        "SSS": "✨ 传奇人生！你的一生如同史诗般波澜壮阔，被后人永远铭记！",
        "SS": "🌟 非凡人生！你的成就超越了绝大多数人，成为时代的标杆。",
        "S": "⭐ 精彩人生！你活出了自己的精彩，留下了许多值得回忆的故事。",
        "A": "👍 充实人生！你经历了酸甜苦辣，人生丰富多彩。",
        "B": "😊 平凡人生！虽然没有大起大落，但也有属于自己的幸福。",
        "C": "😐 平淡人生！你的生活相对单调，但至少平安度过。",
        "D": "😢 坎坷人生！你经历了许多困难，但坚持到了最后。",
        "F": "💀 短暂人生！你的生命过早地画上了句号，令人惋惜。"
    }
    comment = comments.get(grade, "")
    best = max(attrs, key=attrs.get)
    best_names = {"strength": "力量", "intelligence": "智力", "charisma": "魅力", "luck": "运气"}
    comment += f"\n你最突出的属性是{best_names.get(best, best)}（{attrs[best]}），享年{alive_years}岁。"
    return comment


@dataclass
class GameState:
    stage: str = "init"
    world: str = ""
    gender: str = ""
    player_name: str = ""
    player_nickname: str = ""
    sender_id: str = ""
    identity: dict = field(default_factory=dict)
    attrs: dict = field(default_factory=lambda: {"strength": 5, "intelligence": 5, "charisma": 5, "luck": 5})
    talents: list = field(default_factory=list)
    free_points: int = 0
    age: int = 0
    max_age: int = 80
    events_history: list = field(default_factory=list)
    important_choices: list = field(default_factory=list)
    current_important: dict = field(default_factory=dict)
    scheduled_events: dict = field(default_factory=dict)
    alive: bool = True
    pending_input: str = ""
    last_active: float = 0


def generate_scheduled_events(max_age: int) -> dict:
    scheduled = {}
    upper = max_age + 20
    for decade_start in range(1, upper + 1, 10):
        d_end = min(decade_start + 9, upper)
        ages_in_decade = list(range(decade_start, d_end + 1))
        eligible = [e for e in IMPORTANT_EVENTS if e["age_range"][0] <= d_end and e["age_range"][1] >= decade_start]
        if not eligible:
            continue
        random.shuffle(eligible)
        pool_idx = 0
        if len(ages_in_decade) < 2:
            for age in ages_in_decade:
                if pool_idx >= len(eligible):
                    random.shuffle(eligible)
                    pool_idx = 0
                scheduled[age] = eligible[pool_idx]
                pool_idx += 1
            continue
        event_count = min(random.randint(2, 3), len(ages_in_decade))
        chosen_ages = sorted(random.sample(ages_in_decade, event_count))
        for age in chosen_ages:
            if pool_idx >= len(eligible):
                random.shuffle(eligible)
                pool_idx = 0
            scheduled[age] = eligible[pool_idx]
            pool_idx += 1
    logger.info(f"Generated {len(scheduled)} scheduled events for max_age={max_age}, upper={upper}")
    return scheduled


QQ_MSG_LIMIT = 800
GAME_TIMEOUT = 300
AUTO_ADVANCE_STEPS = 5


class LifeSimPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context, config)
        self.config = config or {}
        self.games: Dict[str, GameState] = {}
        self._lock = asyncio.Lock()
        self.provider = None
        self.client = None
        self.model = None
        provider_id = self.config.get("provider_id", "")
        if provider_id:
            try:
                self.provider = context.get_provider_by_id(provider_id)
                if self.provider:
                    logger.info(f"Using AstrBot provider: {provider_id}")
                else:
                    logger.warning(f"Provider '{provider_id}' not found, falling back to manual config")
            except Exception as e:
                logger.warning(f"Failed to get provider '{provider_id}': {e}")
        if not self.provider:
            try:
                key = self.config.get("api_key", "")
                url = self.config.get("api_url", "https://api.openai.com/v1")
                model = self.config.get("model", "gpt-3.5-turbo")
                if key:
                    self.client = openai.AsyncOpenAI(api_key=key, base_url=url)
                    self.model = model
                    logger.info(f"LLM client initialized: model={model}, url={url}")
                else:
                    logger.warning("No provider selected and no API key configured")
            except Exception as e:
                logger.error(f"Failed to initialize LLM client: {e}")

    def _player_id(self, event: AstrMessageEvent) -> str:
        gid = event.get_group_id()
        sid = event.get_sender_id()
        return f"{gid}_{sid}" if gid else sid

    def _get_game(self, event: AstrMessageEvent) -> Optional[GameState]:
        return self.games.get(self._player_id(event))

    def _args(self, event: AstrMessageEvent) -> str:
        text = event.message_str.strip()
        parts = text.split(maxsplit=1)
        result = parts[1].strip() if len(parts) >= 2 else ""
        return result[:200]

    def _attr_text(self, attrs: dict) -> str:
        return f"💪{attrs['strength']} 🧠{attrs['intelligence']} ✨{attrs['charisma']} 🍀{attrs['luck']}"

    async def _get_response(self, system: str, user: str, temperature: float = 0.85, max_tokens: int = 600) -> str:
        if self.provider:
            try:
                llm_resp = await self.provider.text_chat(
                    prompt=user,
                    system_prompt=system,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                if llm_resp and llm_resp.completion_text:
                    return llm_resp.completion_text
                raise RuntimeError("Provider returned empty response")
            except Exception as e:
                logger.error(f"Provider text_chat failed: {e}")
                raise RuntimeError(f"模型调用失败: {e}") from e
        if self.client:
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return resp.choices[0].message.content
            except openai.APIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise RuntimeError(f"API 调用失败: {e}") from e
            except Exception as e:
                logger.error(f"LLM request failed: {traceback.format_exc()}")
                raise RuntimeError(f"请求失败: {e}") from e
        raise RuntimeError("未配置模型，请在插件设置中选择模型或填写 API Key")

    def _build_system_prompt(self, gs: GameState) -> str:
        talent_names = [t["name"] for t in gs.talents]
        return (
            f"你是一个人生模拟游戏的叙述者，世界观：{gs.world}，"
            f"玩家角色名{gs.player_name}，身份{gs.identity.get('name', '普通人')}，性别{gs.gender}，"
            f"天赋：{', '.join(talent_names) or '无'}。"
            f"用第二人称'你'来叙述。每次回复严格控制在50字以内，只写核心剧情，不写多余修饰。"
            f"属性会影响命运：力量低则体弱多灾，智力低则决策失误，魅力低则孤立无援，运气低则厄运频发。"
            f"所有情节必须与世界观、过往经历保持连贯。"
        )

    def _is_group(self, event: AstrMessageEvent) -> bool:
        return bool(event.get_group_id())

    def _respond(self, event: AstrMessageEvent, text: str):
        if self._is_group(event):
            gs = self._get_game(event)
            nickname = ""
            if gs and gs.player_nickname and gs.player_nickname != "N/A":
                nickname = gs.player_nickname
            if not nickname:
                name = event.get_sender_name()
                nickname = name if name and name != "N/A" else event.get_sender_id()
            if gs and gs.stage not in ("init", "choose_gender", "choose_name", "choose_talent", "allocate_points", "dead"):
                char_name = gs.player_name or nickname
                text = f"📖 {char_name}的故事\n{text}"
            return event.make_result().at(nickname, event.get_sender_id()).message(f"\n{text}")
        gs = self._get_game(event)
        if gs and gs.stage not in ("init", "choose_gender", "choose_name", "choose_talent", "allocate_points", "dead"):
            char_name = gs.player_name or "你"
            text = f"📖 {char_name}的故事\n{text}"
        return event.plain_result(text)

    def _split_text(self, text: str, max_len: int = QQ_MSG_LIMIT) -> list:
        if len(text) <= max_len:
            return [text]
        chunks = []
        current = ""
        for line in text.split("\n"):
            if current and len(current) + len(line) + 1 > max_len:
                chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        return chunks if chunks else [text]

    def _touch(self, gs: GameState):
        gs.last_active = time.monotonic()

    def _is_timeout(self, gs: GameState) -> bool:
        if gs.last_active <= 0:
            return False
        return time.monotonic() - gs.last_active > GAME_TIMEOUT

    def _build_story_block(self, gs: GameState, step_msgs: list, add_prompt: bool = True) -> str:
        parts = []
        for msg in step_msgs:
            msg_lines = []
            for line in msg.split("\n"):
                if line.startswith("人生继续"):
                    continue
                if line.startswith("💪"):
                    continue
                msg_lines.append(line)
            if msg_lines:
                parts.append("\n".join(msg_lines))
        lines = ["\n\n".join(parts)] if parts else []
        lines.append(self._attr_text(gs.attrs))
        if gs.age >= gs.max_age - 5:
            lines.append("⚠️ 接近天命")
        if add_prompt:
            lines.append("人生继续 →")
        return "\n".join(lines)

    def _risk_emoji(self, risk: str) -> str:
        return {"低": "🟢", "中": "🟡", "高": "🔴"}.get(risk, "⚪")

    @filter.command("人生帮助", alias={"rlhelp", "rlh"})
    async def cmd_help(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        is_group = self._is_group(event)
        lines = [
            "🎮 模拟人生",
            "",
            "人生开启 <世界观>  开始游戏（rlstart）",
            "人生继续  推进人生（rlnext）",
            "人生选择 <1/2/3>  事件抉择（rlchoose）",
            "人生加点 6 9 9 6  分配属性（rlpoint）",
            "",
            "人生状态 · 人生天赋 · 人生属性",
            "人生世界观 · 人生重置 · 人生帮助",
        ]
        if is_group:
            lines.append("人生排行（rlrank）")
        lines.append("⏱ 5min超时自动结束")
        yield self._respond(event, "\n".join(lines))

    @filter.command("人生世界观", alias={"rlworld", "rlsj"})
    async def cmd_worlds(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        lines = ["🌍 可选世界观"]
        for name, info in WORLDS.items():
            lines.append(f"·{name} {info['desc']}")
        lines.append("·自定义 创建你的专属世界观")
        lines.append("人生开启 <世界观> →")
        yield self._respond(event, "\n".join(lines))

    @filter.command("人生开启", alias={"人生开始", "rlstart", "rlks"})
    async def cmd_start(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        pid = self._player_id(event)
        async with self._lock:
            gs = self._get_game(event)
            if gs and gs.alive:
                if self._is_timeout(gs):
                    logger.info(f"[{pid}] Cleaning timed-out game")
                    del self.games[pid]
                else:
                    yield self._respond(event, "❌ 已在游戏中\n人生重置 →")
                    return
        world_name = self._args(event)
        if not world_name:
            yield self._respond(event, 
                "❌ 请选世界观\n"
                "例: 人生开启 武侠江湖\n"
                "人生世界观 → 查看列表"
            )
            return
        if world_name in WORLDS:
            self.games[pid] = GameState(stage="choose_gender", world=world_name, player_nickname=event.get_sender_name(), sender_id=event.get_sender_id())
            self._touch(self.games[pid])
            logger.info(f"[{pid}] New game started: world={world_name}")
            yield self._respond(event,
                f"🌍 {world_name}\n{WORLDS[world_name]['desc']}\n"
                f"① 选性别 1.男 2.女 3.其他\n"
                f"人生选择 <1/2/3> →"
            )
            return
        self.games[pid] = GameState(stage="choose_gender", world=world_name, player_nickname=event.get_sender_name(), sender_id=event.get_sender_id())
        self._touch(self.games[pid])
        logger.info(f"[{pid}] New game started: custom world={world_name}")
        yield self._respond(event,
            f"🌍 {world_name}\n"
            f"① 选性别 1.男 2.女 3.其他\n"
            f"人生选择 <1/2/3> →"
        )

    @filter.command("人生选择", alias={"rlchoose", "rlxz"})
    async def cmd_choose(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        pid = self._player_id(event)
        async with self._lock:
            gs = self._get_game(event)
            if not gs:
                yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
                return
            if self._is_timeout(gs):
                del self.games[pid]
                logger.info(f"[{pid}] Choose timeout, game deleted")
                yield self._respond(event, "❌ 游戏超时\n人生开启 <世界观> →")
                return
            self._touch(gs)
            choice = self._args(event).strip()
            try:
                yield self._respond(event, await self._handle_choice(pid, gs, choice))
            except Exception as e:
                logger.error(f"cmd_choose error: {traceback.format_exc()}")
                yield self._respond(event, f"❌ 选择处理失败: {e}")

    @filter.command("人生加点", alias={"rlpoint", "rljd"})
    async def cmd_allocate(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        pid = self._player_id(event)
        async with self._lock:
            gs = self._get_game(event)
            if not gs:
                yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
                return
            if gs.stage != "allocate_points":
                yield self._respond(event, "❌ 当前不需要加点\n人生继续 →")
                return
            if self._is_timeout(gs):
                del self.games[pid]
                yield self._respond(event, "❌ 游戏超时\n人生开启 <世界观> →")
                return
            self._touch(gs)
            arg = self._args(event).strip()
            if not arg or arg == "完成":
                if gs.free_points > 0:
                    yield self._respond(event, f"❌ 还有 {gs.free_points} 点未分配\n人生加点 <属性 点数> →")
                    return
                gs.stage = "birth"
                gs.age = 0
                gs.scheduled_events = generate_scheduled_events(gs.max_age)
                logger.info(f"[{pid}] Character created: {gs.player_name}, attrs={gs.attrs}, events={len(gs.scheduled_events)}")
                msg = (
                    f"✅ {gs.player_name} | {gs.identity.get('name', '')}\n"
                    f"{self._attr_text(gs.attrs)}\n"
                    f"⭐ {', '.join(t['name'] for t in gs.talents) or '无'}\n"
                    f"👶 {gs.player_name}诞生了\n"
                    f"人生继续 →"
                )
                yield self._respond(event, msg)
                return
            if arg == "重置":
                gs.attrs = {"strength": 5, "intelligence": 5, "charisma": 5, "luck": 5}
                gs.free_points = 10
                yield self._respond(event, f"已重置\n{self._fmt_attrs(gs.attrs, gs.free_points)}\n人生加点 <属性 点数> →")
                return
            if arg == "随机":
                keys = ["strength", "intelligence", "charisma", "luck"]
                remaining = gs.free_points
                while remaining > 0:
                    gs.attrs[random.choice(keys)] += 1
                    remaining -= 1
                gs.free_points = 0
                yield self._respond(event, f"🎲 随机完成\n{self._attr_text(gs.attrs)}\n人生加点 完成 →")
                return

            attr_names = {"力量": "strength", "智力": "intelligence", "魅力": "charisma", "运气": "luck"}
            nums = arg.split()
            assigned = {}
            if len(nums) == 4 and all(n.isdigit() for n in nums):
                keys = ["strength", "intelligence", "charisma", "luck"]
                for i, key in enumerate(keys):
                    assigned[key] = int(nums[i])
            else:
                i = 0
                while i < len(nums):
                    if i + 1 < len(nums) and nums[i] in attr_names and nums[i + 1].isdigit():
                        assigned[attr_names[nums[i]]] = int(nums[i + 1])
                        i += 2
                    else:
                        yield self._respond(event, "❌ 格式错误\n人生加点 力量 3 智力 2\n人生加点 6 9 9 6")
                        return
            total = sum(assigned.values())
            if total > gs.free_points:
                yield self._respond(event, f"❌ 分配{total}点，仅有{gs.free_points}点\n人生加点 <属性 点数> →")
                return
            for key, val in assigned.items():
                gs.attrs[key] += val
            gs.free_points -= total
            done_hint = "\n人生加点 完成 →" if gs.free_points == 0 else ""
            yield self._respond(event, f"已分配 {total}点 剩余{gs.free_points}点\n{self._attr_text(gs.attrs)}{done_hint}")

    @filter.command("人生天赋", alias={"rltalent", "rltf"})
    async def cmd_talent(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        gs = self._get_game(event)
        if not gs:
            yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
            return
        if not gs.talents:
            yield self._respond(event, "❌ 未获得天赋，请先完成角色创建")
            return
        lines = ["⭐ 天赋"]
        for t in gs.talents:
            lines.append(f"·{t['name']} {t['desc']}")
        if gs.stage not in ("init", "dead"):
            lines.append("人生继续 →")
        yield self._respond(event, "\n".join(lines))

    @filter.command("人生属性", alias={"rlattr", "rlsx"})
    async def cmd_attr(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        gs = self._get_game(event)
        if not gs:
            yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
            return
        lines = [
            f"📊 {gs.player_name or '未命名'} · {gs.age}岁",
            self._attr_text(gs.attrs),
            f"寿命: {gs.max_age}岁"
        ]
        if gs.stage not in ("init", "dead"):
            lines.append("人生继续 →")
        yield self._respond(event, "\n".join(lines))

    @filter.command("人生状态", alias={"rlstatus", "rlzt"})
    async def cmd_status(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        gs = self._get_game(event)
        if not gs:
            yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
            return
        lines = [
            f"📋 {gs.player_name or '未设定'} · {gs.age}岁",
            f"{gs.world} · {gs.identity.get('name', '未设定')} · {gs.gender}",
            self._attr_text(gs.attrs),
            f"寿命: {gs.max_age}岁",
        ]
        if gs.talents:
            lines.append(f"⭐ {', '.join(t['name'] for t in gs.talents)}")
        if gs.important_choices:
            lines.append(f"⚡ 抉择: {len(gs.important_choices)}次")
        if gs.stage not in ("init", "dead"):
            lines.append("人生继续 →")
        yield self._respond(event, "\n".join(lines))

    @filter.command("人生继续", alias={"rlnext", "rljx"})
    async def cmd_next(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        pid = self._player_id(event)
        async with self._lock:
            gs = self._get_game(event)
            if not gs:
                yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")
                return
            if not gs.alive:
                yield self._respond(event, "❌ 人生已结束\n人生开启 <世界观> →")
                return
            if gs.stage in ("init", "choose_gender", "choose_name", "choose_talent", "allocate_points"):
                yield self._respond(event, "❌ 请先完成角色创建\n人生选择 <选项> →")
                return
            if self._is_timeout(gs):
                del self.games[pid]
                yield self._respond(event, "❌ 游戏超时\n人生开启 <世界观> →")
                return
            self._touch(gs)
            if gs.current_important:
                yield self._respond(event, "❌ 先完成当前抉择\n人生选择 <1/2/3> →")
                return
            if gs.stage == "birth":
                gs.age = 1
                gs.stage = "playing"
                if self.provider or self.client:
                    prompt = self._build_system_prompt(gs)
                    user_msg = (
                        f"{gs.player_name}，1岁，{gs.world}。"
                        f"用30-50字描述出生场景。"
                    )
                    try:
                        narrative = await self._get_response(prompt, user_msg, 0.9, 150)
                    except Exception:
                        narrative = "你开始了新的人生。"
                else:
                    narrative = "你开始了新的人生。"
                gs.events_history.append({"age": 1, "text": narrative})
                logger.info(f"[{pid}] Born: age=1, stage=playing")
                yield self._respond(event,
                    f"·1岁 {narrative}\n"
                    f"{self._attr_text(gs.attrs)}\n"
                    f"人生继续 →"
                )
                return
            try:
                logger.info(f"[{pid}] Auto-advance start: age={gs.age}, stage={gs.stage}")
                step_msgs = []
                hit_important = False
                for _ in range(AUTO_ADVANCE_STEPS):
                    gs.age += 1
                    results = await self._advance_life(pid, gs)
                    if not gs.alive:
                        if step_msgs:
                            story = self._build_story_block(gs, step_msgs, add_prompt=False)
                            for chunk in self._split_text(story):
                                yield self._respond(event, chunk)
                        for text in results:
                            yield self._respond(event, text)
                        return
                    if gs.current_important:
                        hit_important = True
                        if step_msgs:
                            story = self._build_story_block(gs, step_msgs, add_prompt=False)
                            for chunk in self._split_text(story):
                                yield self._respond(event, chunk)
                        for text in results:
                            yield self._respond(event, text)
                        return
                    step_msgs.extend(results)
                if step_msgs:
                    story = self._build_story_block(gs, step_msgs)
                    logger.info(f"[{pid}] Auto-advance: batch {AUTO_ADVANCE_STEPS} years, ended at age={gs.age}")
                    for chunk in self._split_text(story):
                        yield self._respond(event, chunk)
            except Exception as e:
                logger.error(f"cmd_next error: {traceback.format_exc()}")
                yield self._respond(event, f"推进人生时出错: {e}")

    @filter.command("人生重置", alias={"rlreset", "rlcz"})
    async def cmd_reset(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        pid = self._player_id(event)
        async with self._lock:
            if pid in self.games:
                logger.info(f"[{pid}] Game reset by player")
                del self.games[pid]
                yield self._respond(event, "✅ 已重置\n人生开启 <世界观> →")
            else:
                yield self._respond(event, "❌ 未开始游戏\n人生开启 <世界观> →")

    @filter.command("人生排行", alias={"rlrank", "rlph"})
    async def cmd_rank(self, event: AstrMessageEvent):
        event.should_call_llm(False)
        if not self._is_group(event):
            yield self._respond(event, "❌ 排行榜仅在群聊中可用！")
            return
        gid = event.get_group_id()
        group_players = []
        for pid, gs in self.games.items():
            if pid.startswith(f"{gid}_"):
                group_players.append(gs)
        if not group_players:
            yield self._respond(event, "群里还没有人开始游戏！\n人生开启 <世界观> →")
            return
        lines = ["🏆 群内排行"]
        for i, gs in enumerate(sorted(group_players, key=lambda g: g.age, reverse=True), 1):
            status = "💀" if not gs.alive else ""
            name = gs.player_name or gs.player_nickname or "未知"
            stage_label = "未出生" if gs.age == 0 else ""
            lines.append(f"{i}.{name}{status} {gs.world} {gs.age}岁{stage_label} {self._attr_text(gs.attrs)}")
        lines.append(f"共{len(group_players)}人")
        text = "\n".join(lines)
        for chunk in self._split_text(text):
            yield self._respond(event, chunk)

    def _random_talents(self, count: int = 3) -> list:
        weighted = []
        for t in TALENTS:
            weighted.extend([t] * t["rarity"])
        selected = []
        pool = list(weighted)
        for _ in range(count):
            if not pool:
                break
            t = random.choice(pool)
            selected.append(t)
            pool = [x for x in pool if x["name"] != t["name"]]
        return selected

    async def _generate_event_content(self, gs: GameState, evt: dict) -> dict:
        fallback = {
            "event_narrative": evt["desc"],
            "choices": [
                {"text": "谨慎应对", "risk": "低", "attr_change": {"intelligence": 2}},
                {"text": "积极面对", "risk": "中", "attr_change": {"charisma": 2}},
                {"text": "冒险一搏", "risk": "高", "attr_change": {"luck": 2}},
            ]
        }
        if not (self.provider or self.client):
            logger.warning("No LLM configured, using fallback event content")
            return fallback
        prompt = (
            "你是人生模拟游戏编剧。生成事件场景和3个选项。\n\n"
            "【场景描述】30-50字，基于事件标题和角色处境，与近期经历有因果关系。\n\n"
            "【选项要求】\n"
            "- 低风险：稳定+2点，8-12字\n"
            "- 中风险：+2-3点，20%额外奖励，8-12字\n"
            "- 高风险：+3-4点，40%惩罚，8-12字（可能导致严重后果）\n"
            "- 属性：strength/intelligence/charisma/luck\n\n"
            "严格JSON输出：\n"
            '{"event_narrative":"场景(30-50字)","choices":[{"text":"行动(8-12字)","risk":"低","attr_change":{"属性":2}},{"text":"...","risk":"中","attr_change":{...}},{"text":"...","risk":"高","attr_change":{...}}]}'
        )
        recent_events = gs.events_history[-3:] if gs.events_history else []
        recent_desc = "；".join(f"{e['age']}岁:{e.get('text', '')[:40]}" for e in recent_events) if recent_events else "暂无"
        important_desc = "无"
        if gs.important_choices:
            last_imp = gs.important_choices[-1]
            important_desc = f"{last_imp['age']}岁{last_imp['event']}，选择：{last_imp['choice']}"
        attr_desc = ", ".join(f"{k}={v}" for k, v in gs.attrs.items())
        user_msg = (
            f"世界观：{gs.world}\n"
            f"角色：{gs.player_name}，{gs.age}岁，{gs.identity.get('name', '普通人')}\n"
            f"当前属性：{attr_desc}\n"
            f"事件标题：{evt['title']}\n"
            f"事件背景：{evt['desc']}\n"
            f"近期经历：{recent_desc}\n"
            f"上次重大抉择：{important_desc}\n"
            f"请生成与近期经历有因果关系的事件场景，不要与之前的经历脱节。"
        )
        try:
            raw = await self._get_response(prompt, user_msg, 0.9, 500)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                raw = raw[start:end]
            parsed = json.loads(raw)
            if isinstance(parsed, dict) and "choices" in parsed:
                event_narrative = parsed.get("event_narrative", evt["desc"])
                choices = parsed["choices"]
                if isinstance(choices, list) and len(choices) == 3:
                    result = []
                    for ch in choices:
                        if isinstance(ch, dict) and "text" in ch and "risk" in ch and "attr_change" in ch:
                            if ch["risk"] not in ("低", "中", "高"):
                                ch["risk"] = "中"
                            for k in list(ch["attr_change"].keys()):
                                if k not in ("strength", "intelligence", "charisma", "luck"):
                                    del ch["attr_change"][k]
                            if ch["attr_change"]:
                                result.append(ch)
                    if len(result) == 3:
                        logger.info(f"AI generated event content for {evt['title']}: {len(result)} choices")
                        return {"event_narrative": event_narrative, "choices": result}
        except Exception as e:
            logger.warning(f"AI event content generation failed: {e}")
        return fallback


    def _fmt_attrs(self, attrs: dict, free_points: int = 0) -> str:
        result = f"💪{attrs['strength']} 🧠{attrs['intelligence']} ✨{attrs['charisma']} 🍀{attrs['luck']}"
        if free_points > 0:
            result += f" | 余{free_points}点"
        return result

    async def _ai_check_death(self, gs: GameState, context: str) -> str | None:
        if self.provider or self.client:
            prompt = (
                "你是人生模拟游戏的死亡裁判官。根据角色当前状态和事件背景，判断角色是否应该死亡。\n\n"
                "【死亡判定规则】\n"
                "- 任意属性极低(≤1)：极高死亡概率\n"
                "- 任意属性低(≤3)：较高死亡概率，尤其在危险事件中\n"
                "- 年龄超过预计寿命：自然老死\n"
                "- 高风险冒险+低属性：大概率死亡\n"
                "- 属性均衡且不太低：一般不会死亡\n\n"
                "严格按JSON输出：\n"
                '{"death":true,"cause":"死亡原因(10字以内)"} 或 {"death":false}'
            )
            attr_desc = f"💪{gs.attrs['strength']} 🧠{gs.attrs['intelligence']} ✨{gs.attrs['charisma']} 🍀{gs.attrs['luck']}"
            user_msg = (
                f"{gs.player_name}，{gs.age}岁/{gs.max_age}岁，{gs.world}。\n"
                f"属性：{attr_desc}\n"
                f"事件：{context}\n"
                f"判断：该角色是否应该死亡？"
            )
            try:
                resp = await self._get_response(prompt, user_msg, 0.7, 100)
                import json as _json
                m = _json.loads(resp.strip().strip("`").strip("json").strip())
                if m.get("death"):
                    return m.get("cause", "意外身亡")
            except Exception:
                pass

        worst = min(gs.attrs.values())
        if worst <= 1:
            return random.choice(["身体衰竭", "精神崩溃", "众叛亲离", "厄运缠身"])
        if worst <= 3 and random.random() < 0.15:
            return random.choice(["积劳成疾", "遭遇不测", "心力交瘁"])
        return None

    async def _handle_choice(self, pid: str, gs: GameState, choice: str) -> str:
        stage = gs.stage

        if stage == "choose_gender":
            gender_map = {"1": "男", "2": "女", "3": "其他"}
            if choice not in gender_map:
                return "❌ 请输入 1-3\n1.男 2.女 3.其他\n人生选择 <1/2/3> →"
            gs.gender = gender_map.get(choice, choice)
            gs.stage = "choose_name"
            return f"性别：{gs.gender}\n② 取个名字\n人生选择 <名字> →"

        if stage == "choose_name":
            gs.player_name = choice.strip() if choice.strip() else "无名"
            gs.identity = random.choice(IDENTITY)
            for attr, val in gs.identity["bonus"].items():
                if attr in gs.attrs:
                    gs.attrs[attr] += val
            bp = []
            for k, v in gs.identity["bonus"].items():
                n = {"strength": "力", "intelligence": "智", "charisma": "魅", "luck": "运"}.get(k, k)
                bp.append(f"{n}+{v}")
            origin_desc = gs.identity["desc"]
            try:
                origin_desc = await self._get_response(
                    "你是一个人生模拟游戏的叙述者。根据世界观和出身类型，用一句话（30-60字）描述角色的出身背景，语言简洁生动。",
                    f"世界观：{gs.world}\n角色名：{gs.player_name}\n性别：{gs.gender}\n出身类型：{gs.identity['name']}（{gs.identity['desc']}）",
                    0.9, 100
                )
                origin_desc = origin_desc.strip()
            except Exception:
                logger.warning(f"AI origin description failed, using default")
            gs.stage = "choose_talent"
            talents = self._random_talents(5)
            gs.current_important = {"talents": talents}
            lines = [
                f"🏠 {gs.identity['name']}({','.join(bp)})",
                origin_desc,
                f"③ 天赋觉醒（5选3）"
            ]
            for i, t in enumerate(talents, 1):
                lines.append(f"{i}.{t['name']} {t['desc']}")
            lines.append(f"人生选择 1 3 5 →")
            return "\n".join(lines)

        if stage == "choose_talent":
            talents = gs.current_important.get("talents", [])
            nums = choice.replace(",", " ").replace("，", " ").split()
            indices = []
            for n in nums:
                try:
                    idx = int(n) - 1
                    if 0 <= idx < len(talents) and idx not in indices:
                        indices.append(idx)
                except ValueError:
                    pass
            if len(indices) < 3:
                opts = [f"{i}.{t['name']}" for i, t in enumerate(talents, 1)]
                return f"❌ 请选择3个天赋\n" + " ".join(opts) + f"\n人生选择 1 3 5 →"
            chosen_list = [talents[i] for i in indices[:3]]
            gs.talents.extend(chosen_list)
            for chosen in chosen_list:
                for attr, val in chosen["bonus"].items():
                    if attr in gs.attrs:
                        gs.attrs[attr] += val
            max_age_bonus = sum(ch["bonus"].get("max_age", 0) for ch in chosen_list)
            gs.max_age = calc_max_age(gs.attrs["strength"], gs.attrs["luck"], max_age_bonus)
            gs.current_important = {}
            gs.stage = "allocate_points"
            gs.free_points = 10
            names = " + ".join(ch["name"] for ch in chosen_list)
            return (
                f"⭐ {names}\n"
                f"📊 自由加点 +10\n{self._fmt_attrs(gs.attrs, gs.free_points)}\n"
                f"人生加点 力量 3 智力 2 / 6 9 9 6 / 随机 / 完成"
            )

        if stage == "allocate_points":
            if choice in ("完成", "done", "ok"):
                gs.stage = "birth"
                gs.scheduled_events = generate_scheduled_events(gs.max_age)
                world_info = WORLDS.get(gs.world, {})
                start_desc = world_info.get("start", "你来到了这个世界。")
                prompt = self._build_system_prompt(gs)
                user_msg = (
                    f"玩家{gs.player_name}（{gs.gender}性，{gs.identity.get('name', '普通人')}）刚刚出生。"
                    f"世界观：{gs.world}。{start_desc}。"
                    f"请用2-3句话描述出生时的场景。"
                )
                if self.provider or self.client:
                    try:
                        birth_narrative = await self._get_response(prompt, user_msg, 0.9, 200)
                    except Exception:
                        birth_narrative = start_desc
                else:
                    birth_narrative = start_desc
                gs.events_history.append({"age": 0, "text": birth_narrative})
                return (
                    f"── {gs.player_name}·0岁 ──\n"
                    f"{birth_narrative}\n"
                    f"🧑 {gs.player_name} | {gs.gender} | {gs.identity.get('name', '')}\n"
                    f"⭐ {' + '.join(t['name'] for t in gs.talents) if gs.talents else '无'}\n"
                    f"{self._attr_text(gs.attrs)}\n"
                    f"⏳ 预计寿命：{gs.max_age}岁\n"
                    f"人生继续 →"
                )

            attr_map = {"力量": "strength", "智力": "intelligence", "魅力": "charisma", "运气": "luck"}
            tokens = choice.split()
            if len(tokens) < 2 or len(tokens) % 2 != 0:
                return (
                    f"❌ 格式错误\n"
                    f"人生加点 力量 3 智力 2\n"
                    f"人生加点 6 9 9 6（力 智 魅 运）\n"
                    f"{self._fmt_attrs(gs.attrs, gs.free_points)}"
                )
            allocated = 0
            details = []
            i = 0
            while i < len(tokens):
                attr_name = tokens[i]
                attr_key = attr_map.get(attr_name)
                if not attr_key:
                    return f"❌ 未知属性 '{attr_name}'\n可选：力量/智力/魅力/运气"
                try:
                    points = int(tokens[i + 1])
                except ValueError:
                    return f"❌ '{tokens[i + 1]}' 不是数字"
                if points < 0:
                    return "❌ 不能为负数"
                allocated += points
                if allocated > gs.free_points:
                    return f"❌ 仅有 {gs.free_points} 点，已尝试 {allocated} 点"
                gs.attrs[attr_key] += points
                details.append(f"{attr_name}+{points}")
                i += 2
            gs.free_points -= allocated
            detail_text = "、".join(details)
            if gs.free_points > 0:
                return (
                    f"{detail_text}\n"
                    f"{self._fmt_attrs(gs.attrs, gs.free_points)}\n"
                    f"人生加点 / 人生加点 完成"
                )
            gs.stage = "birth"
            gs.scheduled_events = generate_scheduled_events(gs.max_age)
            world_info = WORLDS.get(gs.world, {})
            start_desc = world_info.get("start", "你来到了这个世界。")
            prompt = self._build_system_prompt(gs)
            user_msg = (
                f"玩家{gs.player_name}（{gs.gender}性，{gs.identity.get('name', '普通人')}）刚刚出生。"
                f"世界观：{gs.world}。{start_desc}。"
                f"请用2-3句话描述出生时的场景。"
            )
            if self.provider or self.client:
                try:
                    birth_narrative = await self._get_response(prompt, user_msg, 0.9, 200)
                except Exception:
                    birth_narrative = start_desc
            else:
                birth_narrative = start_desc
            gs.events_history.append({"age": 0, "text": birth_narrative})
            return (
                f"✅ {detail_text}\n"
                f"── {gs.player_name}·0岁 ──\n"
                f"{birth_narrative}\n"
                f"🧑 {gs.player_name} | {gs.gender} | {gs.identity.get('name', '')}\n"
                f"⭐ {' + '.join(t['name'] for t in gs.talents) if gs.talents else '无'}\n"
                f"{self._attr_text(gs.attrs)}\n"
                f"⏳ 预计寿命：{gs.max_age}岁\n"
                f"人生继续 →"
            )

        if stage == "important_event":
            evt = gs.current_important
            choices = evt.get("choices", [])
            narrative = evt.get("narrative", evt.get("desc", ""))
            if choice in ("4", "自定义"):
                custom = "" if choice == "4" else choice
                gs.important_choices.append({"age": gs.age, "event": evt.get("title", ""), "choice": f"自定义: {custom}" if custom else "自定义"})
                gs.current_important = {}
                gs.stage = "playing"
                prompt = self._build_system_prompt(gs)
                user_msg = (
                    f"玩家{gs.player_name}在{gs.age}岁时发生了重要事件：{evt.get('title', '')}，"
                    f"事件详情：{narrative}，玩家选择了自定义行动：{custom or '自行决定'}。"
                    f"请描述结果和对属性的影响（50-150字）。"
                )
                try:
                    result = await self._get_response(prompt, user_msg, 0.9, 150)
                except Exception:
                    result = f"你在{gs.age}岁时做出了一个大胆的决定。"
                death_cause = await self._ai_check_death(gs, f"{evt.get('title', '')}：自定义行动 {custom or '自行决定'}")
                if death_cause:
                    logger.info(f"[{pid}] AI judged death at age {gs.age}: {death_cause}")
                    return [f"⚡ {evt.get('title', '')}\n{result}\n💀 {death_cause}，享年{gs.age}岁"]
                logger.info(f"[{pid}] Important event choice: custom at age {gs.age}")
                return f"⚡ {evt.get('title', '')}\n{result}\n{self._attr_text(gs.attrs)}\n人生继续 →"
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(choices):
                    ch = choices[idx]
                    choice_text = ch["text"]
                    attr_change = ch.get("attr_change", {})
                    risk = ch.get("risk", "低")
                    gs.important_choices.append({"age": gs.age, "event": evt.get("title", ""), "choice": choice_text, "risk": risk})
                    for attr, val in attr_change.items():
                        if attr in gs.attrs:
                            gs.attrs[attr] += val
                    risk_outcome = ""
                    attr_names = {"strength": "力量", "intelligence": "智力", "charisma": "魅力", "luck": "运气"}
                    if risk == "高" and random.random() < 0.4:
                        penalty_attr = random.choice(["strength", "intelligence", "charisma", "luck"])
                        penalty = random.randint(1, 3)
                        gs.attrs[penalty_attr] -= penalty
                        risk_outcome = f"\n⚠️ {attr_names[penalty_attr]}-{penalty}！"
                    elif risk == "中" and random.random() < 0.2:
                        bonus_attr = random.choice(["strength", "intelligence", "charisma", "luck"])
                        bonus = 1
                        gs.attrs[bonus_attr] += bonus
                        risk_outcome = f"\n🍀 {attr_names[bonus_attr]}+{bonus}"
                    gs.current_important = {}
                    gs.stage = "playing"
                    prompt = self._build_system_prompt(gs)
                    user_msg = (
                        f"{gs.player_name}，{gs.age}岁，事件：{evt.get('title', '')}，"
                        f"选择了：{choice_text}（{risk}风险）。用30-50字描述结果。"
                    )
                    try:
                        result = await self._get_response(prompt, user_msg, 0.9, 150)
                    except Exception:
                        result = f"你选择了{choice_text}。"
                    death_cause = await self._ai_check_death(gs, f"{evt.get('title', '')}：{choice_text}（{risk}风险）")
                    if death_cause:
                        logger.info(f"[{pid}] AI judged death at age {gs.age}: {death_cause}")
                        return [f"⚡ {evt.get('title', '')}\n{result}{risk_outcome}\n💀 {death_cause}，享年{gs.age}岁"]
                    logger.info(f"[{pid}] Important event choice: {choice_text} (risk={risk}) at age {gs.age}")
                    return f"⚡ {evt.get('title', '')}\n{result}{risk_outcome}\n{self._attr_text(gs.attrs)}\n人生继续 →"
                else:
                    opts = []
                    for i, ch in enumerate(choices, 1):
                        risk_icon = self._risk_emoji(ch["risk"])
                        opts.append(f"{i}.[{ch['text']}]{risk_icon}")
                    opts.append(f"4.自定义")
                    return f"❌ 请输入 1-4\n" + "\n".join(opts) + "\n人生选择 <1/2/3> →"
            except ValueError:
                custom_text = choice
                gs.important_choices.append({"age": gs.age, "event": evt.get("title", ""), "choice": f"自定义: {custom_text}"})
                gs.current_important = {}
                gs.stage = "playing"
                prompt = self._build_system_prompt(gs)
                user_msg = (
                    f"{gs.player_name}，{gs.age}岁，事件：{evt.get('title', '')}，"
                    f"自定义行动：{custom_text}。用30-50字描述结果。"
                )
                try:
                    result = await self._get_response(prompt, user_msg, 0.9, 150)
                except Exception:
                    result = f"你做出了一个大胆的决定：{custom_text}"
                logger.info(f"[{pid}] Important event choice: custom({custom_text}) at age {gs.age}")
                return f"⚡ {evt.get('title', '')}\n{result}\n{self._attr_text(gs.attrs)}\n人生继续 →"

        if stage == "playing":
            return "人生继续 →"

        return f"❌ 当前阶段: {stage}，请按提示操作"

    async def _advance_life(self, pid: str, gs: GameState) -> list:
        if gs.age > gs.max_age + 20:
            logger.info(f"[{pid}] Died at age {gs.age}: exceeded max_age+20")
            return await self._handle_death(pid, gs, "寿终正寝，享年" + str(gs.age) + "岁")

        death_chance = calc_death_chance(gs.age, gs.max_age, gs.attrs["luck"], gs.attrs["strength"])
        if random.random() < death_chance:
            causes = ["疾病", "意外", "天灾", "战乱", "衰老"]
            cause = random.choice(causes)
            logger.info(f"[{pid}] Died at age {gs.age}: {cause} (chance={death_chance:.3f})")
            return await self._handle_death(pid, gs, f"{cause}去世，享年{gs.age}岁")

        attr_penalty_msg = ""
        attr_names = {"strength": "力量", "intelligence": "智力", "charisma": "魅力", "luck": "运气"}
        if gs.attrs["luck"] <= 3 and random.random() < 0.3:
            penalty_attr = random.choice(["strength", "intelligence", "charisma"])
            penalty = random.randint(1, 2)
            gs.attrs[penalty_attr] -= penalty
            attr_penalty_msg = f"⚠️ 厄运降临！{attr_names[penalty_attr]}-{penalty}"
        elif gs.attrs["strength"] <= 3 and random.random() < 0.25:
            gs.attrs["strength"] -= 1
            attr_penalty_msg = "⚠️ 体弱多病，力量-1"
        elif gs.attrs["charisma"] <= 3 and random.random() < 0.2:
            gs.attrs["charisma"] -= 1
            attr_penalty_msg = "⚠️ 遭人排挤，魅力-1"

        evt = gs.scheduled_events.get(gs.age)
        if evt and gs.age not in [c.get("age") for c in gs.important_choices if "age" in c]:
            gs.stage = "important_event"
            logger.info(f"[{pid}] Important event at age {gs.age}: {evt['title']}")
            attr_names = {"strength": "力量", "intelligence": "智力", "charisma": "魅力", "luck": "运气"}
            event_content = await self._generate_event_content(gs, evt)
            ai_choices = event_content["choices"]
            event_narrative = event_content["event_narrative"]
            evt_with_choices = dict(evt)
            evt_with_choices["choices"] = ai_choices
            evt_with_choices["narrative"] = event_narrative
            gs.current_important = evt_with_choices
            lines = [f"⚡ {evt['title']} ·{gs.age}岁"]
            lines.append(event_narrative)
            for i, ch in enumerate(ai_choices, 1):
                risk_icon = self._risk_emoji(ch["risk"])
                hint_parts = []
                for ak, av in ch.get("attr_change", {}).items():
                    hint_parts.append(f"{attr_names.get(ak, ak)}{'+' if av > 0 else ''}{av}")
                hint = " ".join(hint_parts)
                lines.append(f"{i}.[{ch['text']}]{risk_icon}{hint}")
            lines.append("4.自定义")
            lines.append("人生选择 <1/2/3> →")
            return ["\n".join(lines)]

        attr_hint = ""
        if gs.attrs["strength"] <= 3:
            attr_hint += "体弱，"
        if gs.attrs["intelligence"] <= 3:
            attr_hint += "愚钝，"
        if gs.attrs["charisma"] <= 3:
            attr_hint += "孤僻，"
        if gs.attrs["luck"] <= 3:
            attr_hint += "厄运连连，"
        if gs.attrs["strength"] >= 9:
            attr_hint += "体魄强健，"
        if gs.attrs["luck"] >= 9:
            attr_hint += "福星高照，"

        if self.provider or self.client:
            prompt = self._build_system_prompt(gs)
            recent = gs.events_history[-3:] if gs.events_history else []
            recent_desc = "；".join(f"{e['age']}岁:{e['text'][:20]}" for e in recent) if recent else "暂无"
            important_desc = "无"
            if gs.important_choices:
                last_important = gs.important_choices[-1]
                important_desc = f"{last_important['age']}岁{last_important['event']}→{last_important['choice'][:15]}"
            user_msg = (
                f"{gs.player_name}，{gs.age}岁，{gs.world}。\n"
                f"属性：💪{gs.attrs['strength']}🧠{gs.attrs['intelligence']}✨{gs.attrs['charisma']}🍀{gs.attrs['luck']}\n"
                f"状态：{attr_hint or '正常'}\n"
                f"近况：{recent_desc}\n"
                f"上次抉择：{important_desc}\n"
                f"用30-50字描述这一年，融入属性状态影响。"
            )
            try:
                narrative = await self._get_response(prompt, user_msg, 0.9, 150)
            except Exception:
                narrative = f"{gs.age}岁，生活继续..."
        else:
            narrative = f"{gs.age}岁，生活继续..."

        if gs.age % 5 == 0:
            if random.random() < 0.5:
                attr_key = random.choice(list(gs.attrs.keys()))
                gs.attrs[attr_key] += 1
                attr_names = {"strength": "力量", "intelligence": "智力", "charisma": "魅力", "luck": "运气"}
                narrative += f"\n(+1{attr_names[attr_key]})"

        gs.events_history.append({"age": gs.age, "text": narrative})

        death_cause = await self._ai_check_death(gs, narrative)
        if death_cause:
            logger.info(f"[{pid}] AI judged death at age {gs.age}: {death_cause}")
            return await self._handle_death(pid, gs, f"{death_cause}，享年{gs.age}岁")

        lines = [f"·{gs.age}岁 {narrative}"]
        if attr_penalty_msg:
            lines.append(attr_penalty_msg)
        lines.append(self._attr_text(gs.attrs))
        if gs.age >= gs.max_age - 5:
            lines.append("⚠️ 接近天命")
        return ["\n".join(lines)]

    async def _handle_death(self, pid: str, gs: GameState, cause: str) -> list:
        gs.alive = False
        gs.stage = "dead"
        score = calc_score(gs.attrs, gs.talents, gs.important_choices, gs.age)
        comment = get_life_comment(score["grade"], gs.attrs, gs.age)
        logger.info(f"[{pid}] Game over: {gs.player_name} died at {gs.age} ({cause}), grade={score['grade']}, score={score['total']}")

        messages = []

        eulogy = ""
        if self.provider or self.client:
            summary_events = [f"{e['age']}岁: {e['text'][:30]}" for e in gs.events_history[-5:]]
            prompt = self._build_system_prompt(gs)
            user_msg = (
                f"玩家{gs.player_name}在{gs.age}岁时{cause}。身份：{gs.identity.get('name', '')}，"
                f"天赋：{', '.join(t['name'] for t in gs.talents) or '无'}，"
                f"关键事件：{'; '.join(summary_events)}。"
                f"请写一段50-100字的人生总结。"
            )
            try:
                eulogy = await self._get_response(prompt, user_msg, 0.9, 200)
            except Exception:
                pass

        death_lines = [
            f"💀 {gs.player_name} ·{gs.age}岁{cause}",
        ]
        if eulogy:
            death_lines.append(eulogy)
        messages.append("\n".join(death_lines))

        score_lines = [
            f"🏆 {score['grade']}级 · 总分{score['total']}",
            f"属性{sum(gs.attrs.values())} 天赋{score['talent_score']} 抉择{score['choice_score']} 年龄{score['year_score']}",
            self._attr_text(gs.attrs),
            f"⭐ {', '.join(t['name'] for t in gs.talents) or '无'}",
            comment,
        ]
        messages.append("\n".join(score_lines))

        if gs.important_choices:
            choices_lines = ["⚡ 关键抉择"]
            for c in gs.important_choices:
                choices_lines.append(f"·{c['age']}岁 {c['event']}: {c['choice']}")
            choices_text = "\n".join(choices_lines)
            for chunk in self._split_text(choices_text):
                messages.append(chunk)

        messages.append("人生开启 <世界观> → 重新开始")

        return messages
