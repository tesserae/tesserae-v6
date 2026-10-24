#!/usr/bin/env python3
"""Add the credit rows (backend/text_sources.json) and the About-this-text
blurbs (data/text_descriptions.json) for the Greek tranche of 2026-10-24.

    grc_tranche_2026-10-24_metadata.py [--repo ROOT]

Idempotent: a work already present is left alone. The JSON is rewritten in the
format the files already use (indent 2 in both).
"""
import argparse
import json
import os

CGL = 'https://github.com/PerseusDL/canonical-greekLit/tree/master/data/'
F1K = 'https://github.com/OpenGreekAndLatin/First1KGreek/tree/master/data/'
ADDED = 'V6 Import (Greek tranche, 2026-10-24)'
LIC = 'Licence: CC BY-SA 4.0.'

# key: (author, work title, source label, url, print source, blurb)
W = {
 'diogenes_laertius.vitae_philosophorum': ('Diogenes Laertius', 'Vitae philosophorum (Lives of Eminent Philosophers)',
  'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 0004.001)', CGL + 'tlg0004/tlg001',
  'Diogenes Laertius, Lives of Eminent Philosophers. R. D. Hicks, ed. Cambridge, MA: Harvard University Press, 1925. (Loeb Greek text.)',
  "Diogenes Laertius wrote the Lives of Eminent Philosophers in the early third century CE, ten books that trace Greek philosophy through the Ionian and the Italian lines of descent. The work gathers biography, anecdote, quoted epigrams, catalogues of writings, and summaries of doctrine for about eighty thinkers. It is the chief surviving source for Epicurus, whose three letters and Principal Doctrines fill Book 10, and for much of what is known about the Stoics, the Cynics, and the early Academy. The text is cited by book, chapter, and section."),
 'plotinus.enneades': ('Plotinus', 'Enneades', 'Open Greek and Latin (First1KGreek, TLG 2000.001)', F1K + 'tlg2000/tlg001',
  'Plotini Enneades. Richard Volkmann, ed. Leipzig: Teubner, 1883-1884. (' + LIC + ')',
  "Plotinus taught in Rome in the third century CE, and his pupil Porphyry arranged his treatises into six groups of nine, the Enneads. They set out a single account of reality as three levels, the One, Intellect, and Soul, and trace how the soul descends into the body and may return. Other treatises take up virtue, beauty, time, eternity, fate, and the nature of matter. The Enneads shaped Neoplatonism and later Christian and Islamic thought. The text is cited by ennead, treatise, and section."),
 'dio_chrysostom.orationes': ('Dio Chrysostom', 'Orationes (Orations 1 to 80, without 14 to 18)',
  'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 0612.001)', CGL + 'tlg0612/tlg001',
  'Dionis Prusaensis quem vocant Chrysostomum quae exstant omnia. H. von Arnim, ed. Berlin: Weidmann, 1893-1896. (' + LIC + ' Orations 14 to 18 are not in the Perseus file.)',
  "Dio of Prusa, called Chrysostom, was a Greek orator of the late first and early second centuries CE who spoke in cities across the Roman East. His eighty orations range from four speeches on kingship addressed to Trajan to the Euboean tale of a poor hunter, the Olympic oration on Phidias' Zeus, and speeches to the cities of Rhodes, Alexandria, and Tarsus. Many treat the virtues of a ruler or the ways a city and its citizens should behave. They are a main source for the culture of the Second Sophistic. The text is cited by oration and section."),
 'heliodorus.aethiopica': ('Heliodorus', 'Aethiopica', 'Open Greek and Latin (First1KGreek, TLG 0658.001)', F1K + 'tlg0658/tlg001',
  "Heliodori Aethiopicorum libri decem. Immanuel Bekker, ed. Leipzig: Teubner, 1855. (" + LIC + ")",
  "The Aethiopica, in ten books, is the longest and most intricate of the surviving Greek romances, written by Heliodorus of Emesa in the third or fourth century CE. It opens at a beach strewn with bodies and a beautiful girl, Charicleia, and works back to her birth in Ethiopia, her love for the Greek Theagenes, and their flight across Egypt. The plot turns on oracles, pirates, a war between Persia and Ethiopia, and a recognition that ends in marriage. The text is cited by book and chapter."),
 'longus.daphnis_et_chloe': ('Longus', 'Daphnis et Chloe', 'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 0561.001)', CGL + 'tlg0561/tlg001',
  'Erotici Scriptores Graeci, vol. 1. Rudolf Hercher, ed. Leipzig: Teubner, 1858. (Repository licence: CC BY-SA 4.0.)',
  "Daphnis and Chloe is a pastoral romance in four books, written in the second century CE by an author named Longus. Two foundlings, raised by a goatherd and a shepherd on Lesbos, grow up together and slowly learn what their feelings are. The seasons, festivals of Pan and the Nymphs, a pirate raid, and a neighboring war frame their courtship, which ends in marriage after their true parents are found. The text is cited by book, chapter, and section."),
 'xenophon_of_ephesus.ephesiaca': ('Xenophon of Ephesus', 'Ephesiaca (An Ephesian Tale)',
  'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 0641.001)', CGL + 'tlg0641/tlg001',
  'Erotici Scriptores Graeci, vol. 1. Rudolf Hercher, ed. Leipzig: Teubner, 1858. (' + LIC + ')',
  "The Ephesiaca, also called the Ephesian Tale of Anthia and Habrocomes, is a Greek romance in five books from about the second century CE. A young couple of Ephesus, married by their parents after an oracle, are parted on a voyage and pass through pirates, slavery, attempted seductions, and near executions before they are reunited. The pace is fast and the episodes are short, which makes it the plainest example of the genre. The text is cited by book, chapter, and section."),
 'socrates_scholasticus.historia_ecclesiastica': ('Socrates Scholasticus', 'Historia ecclesiastica',
  'Open Greek and Latin (First1KGreek, TLG 2057.002)', F1K + 'tlg2057/tlg002',
  "Socrates' Ecclesiastical History. Robert Hussey, ed. Oxford: Clarendon Press, 1893. (" + LIC + ')',
  "Socrates of Constantinople wrote his Ecclesiastical History in seven books, around 440 CE, as a continuation of Eusebius. It covers the years from the accession of Constantine in 305 to 439, with the Arian dispute, the councils of Nicaea and Constantinople, the reign of Julian, and the quarrels over John Chrysostom as its main subjects. Socrates quotes letters and imperial laws at length and writes as a layman for lay readers. The text is cited by book and chapter."),
 'sozomen.historia_ecclesiastica': ('Sozomen', 'Historia ecclesiastica', 'Open Greek and Latin (First1KGreek, TLG 2048.001)', F1K + 'tlg2048/tlg001',
  'Sozomeni Ecclesiastica Historia. Robert Hussey, ed. Oxford: Oxford University Press, 1860. (' + LIC + ')',
  "Sozomen, a lawyer in Constantinople, wrote his Ecclesiastical History in nine books in the 440s CE. It follows Socrates over the same ground, from Constantine to the early fifth century, and adds more on monks, on the church in Persia, and on provincial Palestine, where he grew up. The history is a main source for the reign of Julian and for the monastic movement. The text is cited by book, chapter, and section."),
 'theodoret.historia_ecclesiastica': ('Theodoret of Cyrrhus', 'Historia ecclesiastica', 'Open Greek and Latin (First1KGreek, TLG 4089.003, Parmentier text)', F1K + 'tlg4089/tlg003',
  'Theodoret, Kirchengeschichte. Léon Parmentier, ed. Leipzig: Hinrichs, 1911. (Die griechischen christlichen Schriftsteller 19. ' + LIC + ' The file comes from an OCR of the print and a few lines of the editor\'s apparatus have been cleaned away.)',
  "Theodoret, bishop of Cyrrhus in Syria, wrote his Ecclesiastical History in five books about 450 CE. It begins with the origins of the Arian controversy and ends in 428. Theodoret writes as a participant in the doctrinal disputes of his own church and quotes many letters and imperial documents, some of them found nowhere else. The text is cited by book, chapter, and section."),
 'philostorgius.historia_ecclesiastica': ('Philostorgius', 'Historia ecclesiastica (epitome and fragments)', 'Open Greek and Latin (First1KGreek, TLG 2058.001)', F1K + 'tlg2058/tlg001',
  'Philostorgius, Kirchengeschichte. Joseph Bidez, ed. Leipzig: Hinrichs, 1913. (Die griechischen christlichen Schriftsteller 21. ' + LIC + ' The file comes from an OCR of the print. The German apparatus has been cleaned away where it stood in the running text.)',
  "Philostorgius, an Arian from Cappadocia, wrote a church history in twelve books around 430 CE, covering the years from about 300 to 425. The work is lost, and what remains is the epitome made by the patriarch Photius, with fragments quoted by later writers. Because Philostorgius takes the side of the Arians, it gives the opposite view of the controversy to the orthodox histories of Socrates, Sozomen, and Theodoret. The text is cited by book and paragraph."),
 'anna_comnena.alexias': ('Anna Comnena', 'Alexias', 'Open Greek and Latin (First1KGreek, TLG 2703.001, Schopen text)', F1K + 'tlg2703/tlg001',
  'Annae Comnenae Alexiadis. Ludwig Schopen, ed. Bonn: Weber, 1839. (Corpus Scriptorum Historiae Byzantinae 38. ' + LIC + ' The file comes from an OCR of the print.)',
  "The Alexiad is a history of the reign of the Byzantine emperor Alexios I Komnenos, who ruled from 1081 to 1118, written in fifteen books by his daughter Anna in the middle of the twelfth century. It covers the wars against the Normans under Robert Guiscard, the Pechenegs, and the Turks, and the arrival of the First Crusade. Anna writes in an Atticizing Greek, models her narrative on Thucydides and Polybius, and quotes Homer freely. The text is cited by book and chapter."),
 'nicander.theriaca': ('Nicander of Colophon', 'Theriaca', 'Open Greek and Latin (First1KGreek, TLG 0022.001)', F1K + 'tlg0022/tlg001',
  'Nicander, Theriaca et Alexipharmaca. Otto Schneider, ed. Leipzig: Teubner, 1856. (' + LIC + ')',
  "The Theriaca is a Greek didactic poem of 958 hexameters by Nicander of Colophon, probably of the second century BCE. It describes venomous snakes, spiders, scorpions, and other animals, the symptoms of their bites, and the remedies for each. The language is obscure on purpose, with rare glosses and learned references to myth. Later poets, among them the author of Vergil's Georgics, knew the poem. The text is cited by line."),
 'nicander.alexipharmaca': ('Nicander of Colophon', 'Alexipharmaca', 'Open Greek and Latin (First1KGreek, TLG 0022.002)', F1K + 'tlg0022/tlg002',
  'Nicander, Theriaca et Alexipharmaca. Otto Schneider, ed. Leipzig: Teubner, 1856. (' + LIC + ')',
  "The Alexipharmaca is a Greek didactic poem of 630 hexameters by Nicander of Colophon, the companion to his Theriaca. It lists poisons taken in food and drink, among them aconite, hemlock, and the venom of the sea hare, together with the signs of poisoning and the antidotes. Like the Theriaca it prizes rare words and learned digressions. The text is cited by line."),
 'origen.contra_celsum': ('Origen', 'Contra Celsum', 'Open Greek and Latin (First1KGreek, TLG 2042.001)', F1K + 'tlg2042/tlg001',
  'Origenes Werke, vols. 1 and 2: Contra Celsum. Paul Koetschau, ed. Leipzig: Hinrichs, 1899. (Die griechischen christlichen Schriftsteller 2 and 3. ' + LIC + ' The file comes from an OCR of the print.)',
  "Origen wrote Against Celsus in eight books about 248 CE, in answer to a work by the pagan philosopher Celsus that had attacked Christianity about seventy years before. Origen quotes Celsus passage by passage and replies to each charge, on the Jewish origins of Jesus, miracles, the resurrection, and the nature of God. It is the fullest early defense of Christian belief against a philosophical critic, and most of Celsus' True Doctrine survives only in its quotations. The text is cited by book and chapter."),
 'origen.commentarii_in_evangelium_joannis': ('Origen', 'Commentarii in evangelium Joannis', 'Open Greek and Latin (First1KGreek, TLG 2042.005)', F1K + 'tlg2042/tlg005',
  'Origenes Werke, vol. 4: Der Johanneskommentar. Erwin Preuschen, ed. Leipzig: Hinrichs, 1903. (Die griechischen christlichen Schriftsteller 10. ' + LIC + ' The file comes from an OCR of the print.)',
  "Origen began his Commentary on John in Alexandria about 226 CE and carried it on in Caesarea. Of an original thirty-two books, nine survive in whole or in large part, together with fragments. It reads the Gospel verse by verse as an allegory of the soul's ascent, opening with the Word and the question of what a gospel is. The commentary was the first great work of Christian biblical exegesis in Greek. The text is cited by book and section."),
 'ignatius.epistulae': ('Ignatius of Antioch', 'Epistulae', 'Open Greek and Latin (First1KGreek, TLG 1443.001)', F1K + 'tlg1443/tlg001',
  'The Apostolic Fathers, vol. 1. Kirsopp Lake, ed. and trans. Cambridge, MA: Harvard University Press, 1912. (Loeb Greek text. ' + LIC + ')',
  "Ignatius, bishop of Antioch, wrote seven letters to churches in Asia Minor and Rome while being taken under guard to his death in Rome, about 110 CE. They urge unity around the bishop, warn against false teaching, and treat martyrdom as the way to imitate Christ. The letters are among the earliest witnesses to the three-fold ministry of bishop, presbyters, and deacons. The text is cited by letter, chapter, and section."),
 'clement_of_rome.epistula_i_ad_corinthios': ('Clement of Rome', 'Epistula I ad Corinthios', 'Open Greek and Latin (First1KGreek, TLG 1271.001)', F1K + 'tlg1271/tlg001',
  'The Apostolic Fathers, vol. 1. Kirsopp Lake, ed. and trans. Cambridge, MA: Harvard University Press, 1912. (Loeb Greek text. ' + LIC + ')',
  "The First Letter of Clement is a letter from the church at Rome to the church at Corinth, written about 96 CE, after the Corinthians had removed their presbyters. It calls for order and humility and draws on the Old Testament, on nature, and on the story of Peter and Paul. It ends with a long prayer. It was widely read in the early church and is among the oldest Christian writings outside the New Testament. The text is cited by chapter and section."),
 'clement_of_rome.epistula_ii_ad_corinthios': ('Pseudo-Clement of Rome', 'Epistula II ad Corinthios', 'Open Greek and Latin (First1KGreek, TLG 1271.002)', F1K + 'tlg1271/tlg002',
  'The Apostolic Fathers, vol. 1. Kirsopp Lake, ed. and trans. Cambridge, MA: Harvard University Press, 1912. (Loeb Greek text. ' + LIC + ')',
  "The so-called Second Letter of Clement is in fact a sermon, delivered about the middle of the second century CE and wrongly joined to the First Letter in the manuscripts. It urges its hearers to repent, to keep the baptismal seal unstained, and to live so as to share in the resurrection. It is the oldest surviving Christian sermon outside the New Testament. The text is cited by chapter and section."),
 'didache.didache': ('Didache', 'Didache (The Teaching of the Twelve Apostles)', 'Open Greek and Latin (First1KGreek, TLG 1311.001)', F1K + 'tlg1311/tlg001',
  'The Apostolic Fathers, vol. 1. Kirsopp Lake, ed. and trans. Cambridge, MA: Harvard University Press, 1912. (Loeb Greek text. ' + LIC + ')',
  "The Didache is a short Christian manual of the late first or early second century CE. It opens with the Two Ways, a choice between life and death, and then gives rules for baptism, fasting, prayer, the Eucharist, and the reception of traveling prophets and apostles. It ends with a warning to watch for the end of the age. It is the earliest known church order. The text is cited by chapter and section."),
 'hermas.pastor': ('Hermas', 'Pastor (The Shepherd of Hermas), through Similitude 9.30.2', 'Open Greek and Latin (First1KGreek, TLG 1419.001)', F1K + 'tlg1419/tlg001',
  'The Apostolic Fathers, vol. 2. Kirsopp Lake, ed. and trans. Cambridge, MA: Harvard University Press, 1913. (Loeb Greek text. ' + LIC + ' The file ends at Similitude 9.30.2, where the Greek manuscript ends. The rest of the print is Latin that the OCR read as Greek, and it is left out.)',
  "The Shepherd is a Christian apocalypse of the early second century CE, given in the name of Hermas, a freed slave in Rome. Its five Visions, twelve Mandates, and ten Similitudes come to him from an elderly woman who stands for the church and from an angel in the form of a shepherd. They call on Christians to repent, to keep clear moral rules, and to build the tower of the church from sound stones. It was read as scripture by some churches. The text is cited by book, chapter, and section."),
 'justin_martyr.apologia_i': ('Justin Martyr', 'Apologia I', 'Open Greek and Latin (First1KGreek, TLG 0645.001)', F1K + 'tlg0645/tlg001',
  'S. Iustini Apologiae duae. Gerhard Rauschen, ed. Bonn: Hanstein, 1911. (Florilegium Patristicum 2. ' + LIC + ')',
  "Justin, a philosopher who became a Christian, addressed his First Apology to the emperor Antoninus Pius about 155 CE. He asks that Christians be judged on what they do and not on their name, answers charges of atheism and immorality, and argues that the prophets foretold Christ. The last chapters describe baptism and the Sunday Eucharist, the earliest such account outside the New Testament. The text is cited by chapter."),
 'justin_martyr.apologia_ii': ('Justin Martyr', 'Apologia II', 'Open Greek and Latin (First1KGreek, TLG 0645.002)', F1K + 'tlg0645/tlg002',
  'S. Iustini Apologiae duae. Gerhard Rauschen, ed. Bonn: Hanstein, 1911. (Florilegium Patristicum 2. ' + LIC + ')',
  "Justin's Second Apology is a short appeal to the Roman senate, written soon after the First. It was prompted by the execution of three Christians in Rome on the order of the city prefect Urbicus. Justin defends the teaching of the Christians, argues that the seeds of the Word are found in the philosophers, and notes that he expects to suffer the same fate. The text is cited by chapter."),
 'justin_martyr.dialogus_cum_tryphone': ('Justin Martyr', 'Dialogus cum Tryphone', 'Open Greek and Latin (First1KGreek, TLG 0645.003)', F1K + 'tlg0645/tlg003',
  'Dialogue avec Tryphon. Georges Archambault, ed. Paris: Picard, 1909. (' + LIC + ' The French notes of the print are cleaned out of the text.)',
  "The Dialogue with Trypho is Justin's report of a two-day conversation with a Jewish man, Trypho, held at Ephesus about 135 CE. Justin begins with his own search among the philosophers, then argues from the Old Testament that Christ is the one the prophets announced and that Christians are the new Israel. Trypho raises objections about the law, circumcision, and the Messiah. It is the oldest long Christian work against Judaism. The text is cited by chapter and section."),
 'athenagoras.legatio': ('Athenagoras', 'Legatio pro Christianis', 'Open Greek and Latin (First1KGreek, TLG 1205.001)', F1K + 'tlg1205/tlg001',
  'Athenagoras, Legatio pro Christianis. Edition from the Perseus and First1KGreek files. (' + LIC + ')',
  "Athenagoras of Athens addressed his Embassy for the Christians to the emperors Marcus Aurelius and Commodus about 177 CE. He answers the three charges then made against Christians, atheism, cannibalism, and incest, argues that the Christian God is one and rational, and shows that pagan poets and philosophers had also spoken of one God. It is among the most literary of the second-century apologies. The text is cited by chapter and section."),
 'athenagoras.de_resurrectione': ('Athenagoras', 'De resurrectione mortuorum', 'Open Greek and Latin (First1KGreek, TLG 1205.002)', F1K + 'tlg1205/tlg002',
  'Athenagoras, De resurrectione. Edition from the Perseus and First1KGreek files. (' + LIC + ')',
  "On the Resurrection of the Dead is a short treatise attributed to Athenagoras of Athens, from the later second century CE. It answers philosophical objections that a body that has been dissolved and eaten cannot be raised again. It argues from God's power and purpose and from the nature of human beings, who are made of body and soul together. The text is cited by chapter and section."),
 'theophilus_of_antioch.ad_autolycum': ('Theophilus of Antioch', 'Ad Autolycum', 'Open Greek and Latin (First1KGreek, TLG 1725.001)', F1K + 'tlg1725/tlg001',
  'Theophili Antiocheni ad Autolycum libri tres. J. C. T. Otto, ed. Jena: Mauke, 1861. (Corpus apologetarum 8. ' + LIC + ')',
  "Theophilus, bishop of Antioch, wrote three books To Autolycus about 180 CE, addressed to a pagan friend. The first answers the question of who the Christian God is, the second sets the Greek myths and poets beside the prophets, and the third argues that Moses is older than Homer and the philosophers. The work is the first Christian text to use the word Trinity, and it gives a Christian chronology of the world from creation. The text is cited by book and chapter."),
 'tatian.oratio_ad_graecos': ('Tatian', 'Oratio ad Graecos', 'Open Greek and Latin (First1KGreek, TLG 1766.001)', F1K + 'tlg1766/tlg001',
  'Tatiani Oratio ad Graecos. J. C. T. Otto, ed. Jena: Mauke, 1851. (Corpus apologetarum 6. ' + LIC + ')',
  "Tatian, a Syrian who studied Greek rhetoric and philosophy and became a Christian in Rome, wrote his Address to the Greeks about 165 CE. It rejects Greek culture point by point, attacking the philosophers, the myths, the theater, and the arts, and claims that Moses and the Christian teaching are far older than Greek learning. It is the harshest of the second-century apologies. The text is cited by chapter."),
 'athanasius.de_incarnatione': ('Athanasius', 'De incarnatione verbi', 'Open Greek and Latin (First1KGreek, TLG 2035.002)', F1K + 'tlg2035/tlg002',
  'St. Athanasius on the Incarnation. Archibald Robertson, ed. 2nd ed. London: David Nutt, 1893. (' + LIC + ')',
  "On the Incarnation of the Word is a short treatise by Athanasius of Alexandria, written probably before 335 CE. It asks why the Word of God became a human being. Athanasius answers that humanity had fallen toward death and that only the one who made it could restore it, and he describes the cross and the resurrection as the means. It is the clearest early statement of the doctrine of redemption through the incarnation. The text is cited by chapter and section."),
 'athanasius.contra_arianos_i': ('Athanasius', 'Orationes contra Arianos I', 'Open Greek and Latin (First1KGreek, TLG 2035.130)', F1K + 'tlg2035/tlg130',
  'The Orations of St. Athanasius against the Arians. William Bright, ed. Oxford: Clarendon Press, 1884. (' + LIC + ')',
  "The first of three Orations against the Arians was written by Athanasius in the 340s CE. It describes the beliefs of Arius and his followers, who held that the Son was a creature made from nothing. Athanasius answers them from Scripture and argues that the Son is of the same nature as the Father. The text is cited by chapter."),
 'athanasius.contra_arianos_ii': ('Athanasius', 'Orationes contra Arianos II', 'Open Greek and Latin (First1KGreek, TLG 2035.131)', F1K + 'tlg2035/tlg131',
  'The Orations of St. Athanasius against the Arians. William Bright, ed. Oxford: Clarendon Press, 1884. (' + LIC + ')',
  "The second Oration against the Arians takes up the Arian use of Proverbs 8.22, 'The Lord created me', and other texts that seem to call the Son a creature. Athanasius reads these as referring to the humanity the Son took on. The text is cited by chapter."),
 'athanasius.contra_arianos_iii': ('Athanasius', 'Orationes contra Arianos III', 'Open Greek and Latin (First1KGreek, TLG 2035.132)', F1K + 'tlg2035/tlg132',
  'The Orations of St. Athanasius against the Arians. William Bright, ed. Oxford: Clarendon Press, 1884. (' + LIC + ')',
  "The third Oration against the Arians treats the passages in the Gospel of John in which Jesus speaks of unity with the Father, and the Arian claim that the unity is only one of will. Athanasius argues for a unity of nature, and ends with texts on the ignorance of the Son. The text is cited by chapter."),
 'athanasius.contra_arianos_iv': ('Pseudo-Athanasius', 'Oratio IV contra Arianos', 'Open Greek and Latin (First1KGreek, TLG 2035.117)', F1K + 'tlg2035/tlg117',
  'The Orations of St. Athanasius against the Arians. William Bright, ed. Oxford: Clarendon Press, 1884. (' + LIC + ')',
  "The fourth Oration against the Arians is transmitted with Athanasius' three but is thought to be a later work, directed against Sabellian and Marcellan teaching as well as Arian. It discusses the relation of the Word to God and the sense of the opening of John's Gospel. The attribution to Athanasius is doubtful. The text is cited by chapter."),
 'john_of_damascus.barlaam_et_ioasaph': ('John of Damascus (attributed)', 'Barlaam et Ioasaph', 'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 2934.066)', CGL + 'tlg2934/tlg066',
  'Barlaam and Ioasaph. G. R. Woodward and H. Mattingly, eds. and trans. Cambridge, MA: Harvard University Press, 1914. (Loeb Greek text. ' + LIC + ')',
  "Barlaam and Ioasaph is a Greek prose romance of edification, attributed to John of Damascus and probably written in the tenth or eleventh century. An Indian king persecutes Christians, but his son Ioasaph is converted by the hermit Barlaam and gives up the throne to become an ascetic. Barlaam's teaching is carried by parables, among them the unicorn, the three caskets, and the man in the well. The tale is a Christian reworking of the legend of the Buddha. The text is cited by chapter and section."),
 'enoch.apocalypsis_enochi': ('Enoch', 'Apocalypsis Enochi (the Book of the Watchers, chapters 1 to 32)', 'Open Greek and Latin (First1KGreek, TLG 1463.001)', F1K + 'tlg1463/tlg001',
  'The Old Testament in Greek, vol. 3: Liber Enoch. H. B. Swete, ed. Cambridge: Cambridge University Press, 1905. (' + LIC + ')',
  "The Greek text of the first part of the Book of Enoch, a Jewish work composed in the last centuries BCE. It tells of the angels called Watchers who came down to earth, took human wives, and taught forbidden arts, of the flood that followed, and of Enoch's journeys through heaven and the places of punishment. The Greek survives in an eighth-century manuscript found at Akhmim in Egypt. The text is cited by chapter and verse."),
}
JUL = [
 ('encomium_constantii', 'Encomium Constantii', '001', 'Julian wrote his Panegyric on the emperor Constantius II in 355 CE, when he was a young Caesar in Gaul and Constantius was still his superior. It follows the usual order of an encomium, with the emperor\'s ancestry, his upbringing, his virtues, and his deeds in war and peace. It is a formal speech in an elevated style.'),
 ('encomium_eusebiae', 'Encomium Eusebiae', '002', "This is Julian's praise of Eusebia, the wife of Constantius II, who had supported him at court and helped to win his appointment as Caesar in 355 CE. It speaks of her birth in Thessalonica, her beauty and gentleness, and her influence over her husband."),
 ('de_gestis_imperatoris', 'De rebus gestis imperatoris vel de regno', '003', "This is Julian's second Panegyric on Constantius II, delivered about 356 CE. It looks at the emperor's deeds against Magnentius and the Persians and sets out what a king ought to be, in the manner of the Greek writings on kingship."),
 ('consolatio_de_discessu_salustii', 'Consolatio de discessu Salustii', '004', "Julian wrote this consolation for himself in 358 CE when the praetorian prefect Salutius, his friend and adviser, was recalled from Gaul. He turns to philosophical arguments to find courage for the loss and praises the man he is parting from."),
 ('ad_atheniensis', 'Ad senatum populumque Atheniensium', '005', 'This is the letter Julian sent to the Athenians in 361 CE, in which he explains why he had gone to war against Constantius II and calls on the city to support him. It is the best account in his own words of how he came to be emperor.'),
 ('ad_themistium', 'Ad Themistium philosophum', '006', 'This is a letter of 361 CE to the philosopher Themistius, in which Julian considers the duties of a ruler who also wants to live as a philosopher. It is his reply to a lost letter from Themistius urging him to take up power.'),
 ('ad_heraclium_cynicum', 'Ad Heraclium cynicum', '007', "Julian's Oration 7, delivered in 362 CE, is an attack on a Cynic philosopher named Heracleios, who had insulted the gods in a speech in Antioch. It sets out how a true Cynic should behave and what kinds of myth may properly be told."),
 ('in_matrem_deorum', 'In matrem deorum', '008', "Julian's Hymn to the Mother of the Gods was written in 362 CE, during the festival of Cybele and Attis. It gives a philosophical reading of the myth of Attis as an account of the descent and return of the soul."),
 ('contra_cynicos_ineruditos', 'Contra cynicos ineruditos', '009', "Julian's Oration 6, Against the Uneducated Cynics, was written in 362 CE. It criticizes a group of wandering Cynics who lived without learning, and holds up Diogenes as a model of true Cynicism."),
 ('caesares', 'Caesares (Symposium sive Saturnalia)', '010', "The Caesars, or Saturnalia, is Julian's satire of 361 CE. At a banquet of the gods on Olympus the Roman emperors, from Julius Caesar to Constantine, compete for the first place, and each is judged by the gods. It is a witty and critical account of the emperors by a man who was about to become one."),
 ('in_regem_solem', 'In regem Solem ad Salustium', '011', "Julian's Hymn to King Helios, composed in 362 CE and addressed to Sallust, sets out his religion of the sun as the visible image of the highest god. It draws on Platonic and Neoplatonic thought and on the traditional cult."),
 ('misopogon', 'Misopogon', '012', "The Misopogon, or Beard-Hater, is a satire Julian wrote in Antioch in 362 to 363 CE against the people of the city, who had mocked his beard and his austere manner. He turns the insults on himself and then on them, and shows his view of the city's luxury."),
 ('epistulae', 'Epistulae', '013', "Julian's letters, eighty-three in this collection, run from his years as Caesar in Gaul to his last campaign against Persia. They include letters on his plans for the pagan priesthood, his edict on teachers, and his dealings with cities and friends."),
 ('contra_galilaeos', 'Contra Galilaeos', '017', "Against the Galileans is the fragmentary work in which Julian attacked Christianity in 362 to 363 CE. It survives mainly in the quotations of Cyril of Alexandria, who answered it. Julian argues that Christians have abandoned both Greek and Jewish tradition, and he questions the Gospel accounts."),
]
for stem, title, num, blurb in JUL:
    W[f'julian.{stem}'] = ('Julian the Emperor', title, 'Perseus Digital Library / Open Greek and Latin (canonical-greekLit, TLG 2003.' + num + ')',
        CGL + f'tlg2003/tlg{num}', "The Works of the Emperor Julian. Wilmer Cave Wright, ed. and trans. Cambridge, MA: Harvard University Press, 1913-1923. (Loeb Greek text. " + LIC + ')', blurb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    a = ap.parse_args()
    sp = os.path.join(a.repo, 'backend', 'text_sources.json')
    dp = os.path.join(a.repo, 'data', 'text_descriptions.json')
    src = json.load(open(sp, encoding='utf-8'))
    have = {(r['author'], r['work']) for r in src}
    added = 0
    for key, (author, work, label, url, print_source, _b) in W.items():
        if (author, work) in have:
            continue
        src.append({'author': author, 'work': work, 'e_source': label, 'e_source_url': url,
                    'print_source': print_source, 'added_by': ADDED})
        added += 1
    with open(sp, 'w', encoding='utf-8') as fh:
        json.dump(src, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    desc = json.load(open(dp, encoding='utf-8'))
    g = desc['grc']
    n = 0
    for key, row in W.items():
        if key not in g:
            g[key] = row[5]
            n += 1
    with open(dp, 'w', encoding='utf-8') as fh:
        json.dump(desc, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'sources +{added}, descriptions +{n}, works {len(W)}')


if __name__ == '__main__':
    main()
