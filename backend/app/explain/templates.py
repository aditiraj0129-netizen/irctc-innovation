"""Hand-written Hindi/English explanations. These are the fallback whenever the
LLM is off, slow, or fails validation, so the app always works.

Numbers never appear in these strings: they are slots like {refund} that code
fills in from the rules engine's output.
"""
from __future__ import annotations

from app.plan.models import PlanKind

T: dict[str, dict[PlanKind, tuple[str, str]]] = {
    "en": {
        PlanKind.TRAVEL_AS_BOOKED: ("Travel as booked",
                                    "Nothing has changed. You reach at {arrival}."),
        PlanKind.TRAVEL_DELAYED: ("Wait and travel on your delayed train",
                                  "You keep your ticket and reach at about {arrival}. No money is lost."),
        PlanKind.CANCEL_NOW: ("Cancel now",
                              "If you cancel now you get {refund} back under the current rule."),
        PlanKind.FILE_TDR_LATE: ("Don't travel and file a TDR",
                                 "Your train is more than 3 hours late. File a TDR before the train actually leaves ({deadline}). If approved, you get {refund} back."),
        PlanKind.TDR_LATE_PLUS_ALTERNATIVE: ("File a TDR and take another train",
                                             "File the TDR before your train leaves, then take {trains} to reach at {arrival}. You need a new ticket; seats are not checked."),
        PlanKind.AUTO_REFUND_WAIT: ("Do nothing: refund comes automatically",
                                    "Your waitlisted ticket is dropped after the chart. {refund} comes back automatically, without cancelling."),
        PlanKind.AUTO_REFUND_PLUS_ALTERNATIVE: ("Take another train",
                                                "{refund} comes back automatically. Book {trains} to reach at {arrival}. Seats are not checked; book by {deadline}."),
        PlanKind.TDR_MISSED_CONNECTION_ONLY: ("Stop at the junction and file a TDR",
                                              "Your tickets are linked, so you can file a TDR for the missed train. If approved, you get {refund} back."),
        PlanKind.TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE: ("Take another train and file a TDR",
                                                          "Take {trains} from {station} to reach at {arrival}. Also file a TDR for the missed train; if approved, {refund} comes back. Book by {deadline}."),
        PlanKind.CANCEL_NEXT_LEG_PLUS_ALTERNATIVE: ("Cancel the next train and rebook",
                                                    "Your tickets are not linked. Cancelling the next train now returns {refund}. Then book {trains} to reach at {arrival}."),
        PlanKind.USE_OFFICIAL_CHANNEL: ("Check with the official channel",
                                        "We can't advise safely right now. Check RailOne or IRCTC, or call 139."),
    },
    "hi": {
        PlanKind.TRAVEL_AS_BOOKED: ("बुक की गई यात्रा करें",
                                    "कुछ नहीं बदला है। आप {arrival} पर पहुँचेंगे।"),
        PlanKind.TRAVEL_DELAYED: ("रुकें और अपनी लेट ट्रेन से जाएँ",
                                  "आपका टिकट बना रहता है और आप लगभग {arrival} पर पहुँचेंगे। पैसे का नुकसान नहीं।"),
        PlanKind.CANCEL_NOW: ("अभी कैंसिल करें",
                              "अभी कैंसिल करने पर मौजूदा नियम के अनुसार {refund} वापस मिलेंगे।"),
        PlanKind.FILE_TDR_LATE: ("यात्रा न करें और TDR फाइल करें",
                                 "आपकी ट्रेन 3 घंटे से ज़्यादा लेट है। ट्रेन के असल में छूटने ({deadline}) से पहले TDR फाइल करें। मंज़ूरी मिलने पर {refund} वापस मिलेंगे।"),
        PlanKind.TDR_LATE_PLUS_ALTERNATIVE: ("TDR फाइल करें और दूसरी ट्रेन लें",
                                             "अपनी ट्रेन छूटने से पहले TDR फाइल करें, फिर {trains} से {arrival} तक पहुँचें। नया टिकट लेना होगा; सीटें जाँची नहीं गई हैं।"),
        PlanKind.AUTO_REFUND_WAIT: ("कुछ न करें: रिफंड अपने आप आएगा",
                                    "चार्ट के बाद वेटिंग टिकट हट जाता है। {refund} बिना कैंसिल किए अपने आप वापस आएँगे।"),
        PlanKind.AUTO_REFUND_PLUS_ALTERNATIVE: ("दूसरी ट्रेन लें",
                                                "{refund} अपने आप वापस आएँगे। {arrival} तक पहुँचने के लिए {trains} बुक करें। सीटें जाँची नहीं गई हैं; {deadline} तक बुक करें।"),
        PlanKind.TDR_MISSED_CONNECTION_ONLY: ("जंक्शन पर रुकें और TDR फाइल करें",
                                              "आपके टिकट लिंक हैं, इसलिए छूटी ट्रेन के लिए TDR फाइल कर सकते हैं। मंज़ूरी मिलने पर {refund} वापस मिलेंगे।"),
        PlanKind.TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE: ("दूसरी ट्रेन लें और TDR फाइल करें",
                                                          "{station} से {trains} लेकर {arrival} तक पहुँचें। छूटी ट्रेन के लिए TDR भी फाइल करें; मंज़ूरी मिलने पर {refund} वापस आएँगे। {deadline} तक बुक करें।"),
        PlanKind.CANCEL_NEXT_LEG_PLUS_ALTERNATIVE: ("अगली ट्रेन कैंसिल करके दोबारा बुक करें",
                                                    "आपके टिकट लिंक नहीं हैं। अगली ट्रेन अभी कैंसिल करने पर {refund} वापस मिलेंगे। फिर {arrival} तक पहुँचने के लिए {trains} बुक करें।"),
        PlanKind.USE_OFFICIAL_CHANNEL: ("आधिकारिक माध्यम से जाँचें",
                                        "अभी हम सुरक्षित सलाह नहीं दे सकते। RailOne या IRCTC देखें, या 139 पर कॉल करें।"),
    },
}
