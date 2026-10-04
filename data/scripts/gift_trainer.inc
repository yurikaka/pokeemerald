MysteryGiftScript_VisitingTrainer::
	setvaddress MysteryGiftScript_VisitingTrainer
	special ValidateEReaderTrainer
	vgoto_if_eq VAR_RESULT, 0, MysteryGiftScript_VisitingTrainerArrived
	lock
	faceplayer
	vmessage sText_MysteryGiftVisitingTrainerInstructions
	waitmessage
	waitbuttonpress
	release
	end

MysteryGiftScript_VisitingTrainerArrived:
	lock
	faceplayer
	vmessage sText_MysteryGiftVisitingTrainerArrived
	waitmessage
	waitbuttonpress
	release
	end

sText_MysteryGiftVisitingTrainerInstructions:
	.string "感谢使用\n神秘礼物系统。\p由于拥有神秘卡片\n您可以在友好商店\l参与调查。\p通过调查您可以邀请\n训练家去琉璃市。\p……让我给您一个\n调查的密码吧：\p“GIVE ME\nAWESOME TRAINER”\p把这个写在调查上并发送到\n无线连接系统。$"

sText_MysteryGiftVisitingTrainerArrived:
	.string "感谢使用\n神秘礼物系统。\p一位训练家已经来到\n琉璃市寻找您。\p希望您可以享受\n与训练家的对战。\p您可以邀请其他训练家\n通过填写密码。\p试着找寻其他\n有用的密码吧。$"
