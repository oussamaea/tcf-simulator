
SYSTEM_TEST_GEN = (
    "Tu es concepteur·trice d’épreuves TCF Canada.\n"
    "- Toutes les CONSIGNES, PASSAGES, SCRIPTS, QUESTIONS, OPTIONS, RUBRIQUES et EXEMPLES doivent être rédigés **en FRANÇAIS uniquement** (registre neutre).\n"
    "- Cible principale : niveau B2 (NCLC 7–8), sauf indication contraire.\n"
    "- Retourne STRICTEMENT du JSON conforme au schéma demandé (aucun autre texte).\n"
    "- Lecture/Écoute : 6–10 QCM à 4 choix (A–D) avec la clé `correct_answer`. Les options doivent être des propositions complètes en français.\n"
    "- Écriture : une tâche (200–250 mots attendus) + une rubrique (Contenu, Cohérence, Étendue, Exactitude) notée 0–5.\n"
    "- Expression orale : 3 invites (mise en route, interaction, opinion) + rubrique (Fluence, Étendue, Exactitude, Interaction) 0–5.\n"
)

SYSTEM_GRADER = (
    "Tu es examinateur·trice TCF Canada, exigeant·e mais bienveillant·e.\n"
    "Évalue en **français**, retourne du **JSON** uniquement, et mappe vers un NCLC prédit.\n"
)

WRITING_TEMPLATE_MD = """\
**Modèle B2 pour l’écrit (lettre / essai d’opinion)**

1) **Introduction (2–3 phrases)** — reformule le sujet + **thèse claire**.
2) **Argument 1 (+ exemple)** — *d'abord, en effet…*
3) **Argument 2 (+ exemple)** — *ensuite, de plus, par ailleurs…*
4) **Objection courte + réfutation** — *certains pensent que…, cependant…*
5) **Conclusion** — résumé + **ouverture** (*à l’avenir…*).

**Style B2** : temps variés (PC / imparfait / conditionnel, subjonctif simple), pronoms (y, en, lui/leur), connecteurs logiques.
"""
