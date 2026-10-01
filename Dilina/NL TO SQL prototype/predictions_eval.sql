SELECT COUNT(*) FROM singer;	concert_singer
SELECT count(*) FROM singer;	concert_singer
SELECT Name, Country, Age FROM singer ORDER BY Age DESC;	concert_singer
SELECT Name, Country, Age FROM singer ORDER BY Age DESC;	concert_singer
SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';	concert_singer
SELECT avg(Age), min(Age), max(Age) FROM singer WHERE Country = 'France';	concert_singer
SELECT Song_Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer)	concert_singer
SELECT Song_Name, Song_release_year FROM singer WHERE Age = (SELECT MIN(Age) FROM singer);	concert_singer
SELECT DISTINCT Country FROM singer WHERE Age > 20;	concert_singer
SELECT DISTINCT Country FROM singer WHERE Age > 20;	concert_singer
SELECT Country, COUNT(*) FROM singer GROUP BY Country;	concert_singer
SELECT Country, COUNT(*) FROM singer GROUP BY Country;	concert_singer
SELECT Song_Name FROM singer WHERE Age > (SELECT AVG(Age) FROM singer)	concert_singer
SELECT Song_Name FROM singer WHERE Age > (SELECT AVG(Age) FROM singer)	concert_singer
SELECT Location, Name FROM stadium WHERE Capacity BETWEEN 5000 AND 10000;	concert_singer
SELECT Location, Name FROM stadium WHERE Capacity BETWEEN 5000 AND 10000;	concert_singer
SELECT MAX(capacity), AVG(capacity) FROM stadium;	concert_singer
SELECT avg(Capacity), max(Capacity) FROM stadium;	concert_singer
SELECT Name, Capacity FROM stadium ORDER BY Average DESC LIMIT 1;	concert_singer
SELECT Name, Capacity FROM stadium ORDER BY Average DESC LIMIT 1;	concert_singer
SELECT COUNT(*) FROM concert WHERE Year IN (2014, 2015);	concert_singer
SELECT COUNT(*) FROM concert WHERE YEAR IN (2014, 2015);	concert_singer
SELECT t1.Name, COUNT(t2.concert_ID) FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID GROUP BY t1.Stadium_ID;	concert_singer
SELECT t1.Name, COUNT(t2.concert_ID) FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID GROUP BY t1.Stadium_ID;	concert_singer
SELECT t1.name, t1.capacity FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID WHERE t2.Year >=2014 GROUP BY t1.Stadium_ID ORDER BY COUNT(t2.concert_ID) DESC LIMIT 1;	concert_singer
SELECT t1.name, t1.capacity FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID WHERE t2.Year >2013 GROUP BY t1.Stadium_ID ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Year FROM concert GROUP BY Year ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Year FROM concert GROUP BY Year ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert);	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert);	concert_singer
SELECT Country FROM singer WHERE Age >40 INTERSECT SELECT Country FROM singer WHERE Age < 30;	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert WHERE Year = '2014')	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert WHERE Year = '2014')	concert_singer
SELECT c.concert_Name, c.Theme, COUNT(sic.Singer_ID) AS Number_of_Singers FROM concert AS c LEFT JOIN singer_in_concert AS sic ON c.concert_ID = sic.concert_ID GROUP BY c.concert_ID, c.concert_Name, c.Theme;	concert_singer
SELECT T3.concert_Name, T3.Theme, COUNT(T4.Singer_ID) FROM concert AS T3 JOIN singer_in_concert AS T4 ON T3.concert_ID = T4.concert_ID GROUP BY T3.concert_Name, T3.Theme;	concert_singer
SELECT T1.Name, COUNT(T2.concert_ID) FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Singer_ID;	concert_singer
SELECT T1.Name, COUNT(T2.concert_ID) FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Name;	concert_singer
SELECT DISTINCT T3.Name FROM concert AS T1 JOIN singer_in_concert AS T2 ON T1.concert_ID = T2.concert_ID JOIN singer AS T3 ON T2.Singer_ID = T3.Singer_ID WHERE T1.Year = 2014;	concert_singer
SELECT DISTINCT T1.Name FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID JOIN concert AS T3 ON T2.concert_ID = T3.concert_ID WHERE T3.Year = 2014;	concert_singer
SELECT Name, Country FROM singer WHERE Song_Name LIKE '%Hey%';	concert_singer
SELECT Name, Country FROM singer WHERE Song_Name LIKE '%Hey%';	concert_singer
SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year =2014 INTERSECT SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = 2015;	concert_singer
SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year =2014 INTERSECT SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = 2015;	concert_singer
SELECT COUNT(*) FROM concert AS t1 JOIN stadium AS t2 ON t1.Stadium_ID = t2.Stadium_ID WHERE t2.Capacity = (SELECT MAX(Capacity) FROM stadium);	concert_singer
SELECT COUNT(*) FROM concert WHERE Stadium_ID = (SELECT Stadium_ID FROM stadium ORDER BY Capacity DESC LIMIT 1);	concert_singer
SELECT COUNT(*) FROM Pets WHERE weight > 10;	pets_1
SELECT COUNT(*) FROM Pets WHERE weight > 10;	pets_1
SELECT weight FROM Pets WHERE PetType = 'dog' ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT weight FROM Pets WHERE PetType = 'dog' ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT PetType, MAX(weight) AS max_weight FROM Pets GROUP BY PetType;	pets_1
SELECT PetType, MAX(weight) FROM Pets GROUP BY PetType;	pets_1
SELECT COUNT(*) FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID WHERE Student.age > 20;	pets_1
SELECT COUNT(DISTINCT h.PetID) FROM Student s JOIN Has_Pet h ON s.StuID = h.StuID WHERE s.Age > 20;	pets_1
SELECT COUNT(*) FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Student.Sex = 'F' AND Pets.PetType = 'dog';	pets_1
SELECT COUNT(*) FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID = T2.StuID JOIN Pets AS T3 ON T2.PetID = T3.PetID WHERE T1.Sex = 'F' AND T3.PetType = 'dog';	pets_1
SELECT COUNT(DISTINCT PetType) FROM Pets;	pets_1
SELECT COUNT(DISTINCT PetType) FROM Pets;	pets_1
SELECT Student.Fname FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType IN ('cat', 'dog');	pets_1
SELECT DISTINCT T1.Fname FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID = T2.StuID JOIN Pets AS T3 ON T2.PetID = T3.PetID WHERE T3.PetType = 'cat' OR T3.PetType = 'dog';	pets_1
SELECT DISTINCT S.Fname FROM Student S JOIN Has_Pet HP1 ON S.StuID = HP1.StuID JOIN Pets P1 ON HP1.PetID = P1.PetID JOIN Has_Pet HP2 ON S.StuID = HP2.StuID JOIN Pets P2 ON HP2.PetID = P2.PetID WHERE P1.PetType = 'cat' AND P2.PetType = 'dog';	pets_1
SELECT DISTINCT S.Fname FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'cat' INTERSECT SELECT DISTINCT S.Fname FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'dog';	pets_1
SELECT Major, Age FROM Student WHERE StuID NOT IN ( SELECT StuID FROM Has_Pet JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' );	pets_1
SELECT Major, Age FROM Student WHERE StuID NOT IN ( SELECT StuID FROM Has_Pet JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' );	pets_1
SELECT StuID FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat')	pets_1
SELECT StuID FROM Student EXCEPT SELECT StuID FROM Has_Pet WHERE PetID IN (SELECT PetID FROM Pets WHERE PetType = 'cat')	pets_1
SELECT Student.Fname, Student.Age FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'dog' AND Student.StuID NOT IN ( SELECT Student.StuID FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' );	pets_1
SELECT DISTINCT S.Fname FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'dog' AND S.StuID NOT IN ( SELECT HP.StuID FROM Has_Pet HP JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'cat' );	pets_1
SELECT PetType, weight FROM Pets WHERE pet_age = (SELECT MIN(pet_age) FROM Pets);	pets_1
SELECT PetType, weight FROM Pets ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT PetID, weight FROM Pets WHERE pet_age > 1;	pets_1
SELECT PetID, weight FROM Pets WHERE pet_age > 1;	pets_1
SELECT Pets.PetType, AVG(Pets.pet_age) AS AverageAge, MAX(Pets.pet_age) AS MaximumAge FROM Pets JOIN Has_Pet ON Pets.PetID = Has_Pet.PetID GROUP BY Pets.PetType;	pets_1
SELECT Pets.PetType, AVG(Pets.pet_age), MAX(Pets.pet_age) FROM Pets JOIN Has_Pet ON Pets.PetID = Has_Pet.PetID GROUP BY Pets.PetType;	pets_1
SELECT Pets.PetType, AVG(Pets.weight) FROM Pets GROUP BY Pets.PetType;	pets_1
SELECT Pets.PetType, AVG(Pets.weight) FROM Pets GROUP BY Pets.PetType;	pets_1
SELECT DISTINCT Student.Fname, Student.Age FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID;	pets_1
SELECT DISTINCT Fname, Age FROM Student WHERE StuID IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT T2.PetID FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID = T2.StuID WHERE T1.LName = 'Smith';	pets_1
SELECT T2.PetID FROM Student AS T1 JOIN Has_Pet AS T2 ON T1.StuID = T2.StuID WHERE T1.LName = 'Smith';	pets_1
SELECT Student.StuID, COUNT(Has_Pet.PetID) AS NumberOfPets FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID GROUP BY Student.StuID;	pets_1
SELECT StuID, COUNT(PetID) AS NumberOfPets FROM Has_Pet GROUP BY StuID;	pets_1
SELECT Student.Fname, Student.Sex FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID GROUP BY Student.StuID HAVING COUNT(Has_Pet.PetID) > 1;	pets_1
SELECT Student.Fname, Student.Sex FROM Student WHERE Student.StuID IN ( SELECT Has_Pet.StuID FROM Has_Pet GROUP BY Has_Pet.StuID HAVING COUNT(Has_Pet.PetID) > 1 );	pets_1
SELECT DISTINCT Student.LName FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' AND Pets.pet_age = 3;	pets_1
SELECT Student.LName FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' AND Pets.pet_age = 3;	pets_1
SELECT AVG(age) FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT AVG(age) FROM student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT COUNT(*) FROM continents;	car_1
SELECT count(*) FROM continents;	car_1
SELECT T1.ContId, T1.Continent, COUNT(T2.CountryId) FROM continents AS T1 JOIN countries AS T2 ON T1.ContId = T2.Continent GROUP BY T1.ContId, T1.Continent;	car_1
SELECT c.ContId, c.Continent, COUNT(co.CountryId) AS NumberOfCountries FROM continents c LEFT JOIN countries co ON c.ContId = co.Continent GROUP BY c.ContId, c.Continent;	car_1
SELECT COUNT(*) FROM countries;	car_1
SELECT count(*) FROM countries;	car_1
SELECT cm.FullName, cm.Id, COUNT(ml.Model) AS NumberOfModels FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.FullName, cm.Id;	car_1
SELECT cm.FullName, cm.Id, COUNT(ml.Model) AS ModelCount FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.Id, cm.FullName;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id ORDER BY CAST(REPLACE(T2.Horsepower, ',', '') AS REAL) ASC LIMIT 1;	car_1
SELECT Model FROM car_names WHERE MakeId = (SELECT Id FROM cars_data ORDER BY Horsepower ASC LIMIT 1)	car_1
SELECT Model FROM car_names WHERE MakeId IN (SELECT Id FROM cars_data WHERE Weight < (SELECT AVG(Weight) FROM cars_data))	car_1
SELECT Model FROM car_names WHERE MakeId IN (SELECT Id FROM cars_data WHERE Weight < (SELECT AVG(Weight) FROM cars_data))	car_1
SELECT DISTINCT Maker FROM car_makers WHERE Country = 1;	car_1
SELECT DISTINCT T3.Maker FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T4 ON T2.Model = T4.Model JOIN car_makers AS T3 ON T4.Maker = T3.Id WHERE T1.Year = 1970;	car_1
SELECT T1.Make, T2.Year FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Year = (SELECT MIN(Year) FROM cars_data);	car_1
SELECT T3.Maker, T1.Year FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T3 ON T2.Model = T3.Model ORDER BY T1.Year ASC LIMIT 1;	car_1
SELECT DISTINCT ml.Model FROM model_list ml JOIN car_names cn ON ml.Model = cn.Model JOIN cars_data cd ON cn.MakeId = cd.Id WHERE cd.Year > 1980;	car_1
SELECT DISTINCT T2.Model FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T1.Year > 1980;	car_1
SELECT c.Continent, COUNT(cm.Id) AS MakerCount FROM car_makers cm JOIN countries co ON cm.Country = co.CountryId JOIN continents c ON co.Continent = c.ContId GROUP BY c.Continent;	car_1
SELECT c.Continent, COUNT(cm.Id) AS NumberOfCarMakers FROM continents c JOIN countries co ON c.ContId = co.Continent JOIN car_makers cm ON co.CountryId = cm.Country GROUP BY c.Continent;	car_1
SELECT T3.CountryName FROM car_makers AS T1 JOIN countries AS T3 ON T1.Country = T3.CountryId GROUP BY T3.CountryName ORDER BY COUNT(T1.Id) DESC LIMIT 1;	car_1
SELECT T2.CountryName FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId GROUP BY T2.CountryName ORDER BY COUNT(T1.Id) DESC LIMIT 1;	car_1
SELECT COUNT(T1.Model) , T2.FullName FROM model_list AS T1 JOIN car_makers AS T2 ON T1.Maker = T2.Id GROUP BY T2.FullName;	car_1
SELECT cm.Id, cm.FullName, COUNT(ml.Model) AS NumberOfModels FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.Id, cm.FullName;	car_1
SELECT T2.Accelerate FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id JOIN model_list AS T3 ON T1.Model = T3.Model WHERE T1.Make = 'amc' AND T3.Model = 'hornet sportabout (sw)';	car_1
SELECT T3.Accelerate FROM car_names AS T1 JOIN model_list AS T2 ON T1.Model = T2.Model JOIN cars_data AS T3 ON T1.MakeId = T3.Id JOIN car_makers AS T4 ON T2.Maker = T4.Id WHERE T4.Maker = 'amc' AND T1.Model = 'hornet sportabout (sw)';	car_1
SELECT COUNT(*) FROM car_makers JOIN countries ON car_makers.Country = countries.CountryId WHERE countries.CountryName = 'france';	car_1
SELECT COUNT(*) FROM car_makers JOIN countries ON car_makers.Country = countries.CountryId WHERE countries.CountryName = 'France';	car_1
SELECT COUNT(DISTINCT ml.Model) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN countries c ON cm.Country = c.CountryId WHERE c.CountryName = 'usa';	car_1
SELECT COUNT(DISTINCT ml.Model) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN countries c ON cm.Country = c.CountryId WHERE c.CountryName = 'USA';	car_1
SELECT AVG(MPG) FROM cars_data WHERE Cylinders = 4;	car_1
SELECT AVG(MPG) FROM cars_data WHERE Cylinders = 4;	car_1
SELECT MIN(T1.Weight) FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T3 ON T2.Model = T3.Model WHERE T1.Cylinders = 8 AND T1.Year = 1974;	car_1
SELECT MIN(T1.Weight) FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T1.Cylinders = 8 AND T1.Year = 1974;	car_1
SELECT T2.Maker, T1.Model FROM car_names AS T1 JOIN model_list AS T2 ON T1.Model = T2.Model	car_1
SELECT T2.Maker, T1.Model FROM car_names AS T1 JOIN model_list AS T2 ON T1.Model = T2.Model	car_1
SELECT CountryName, CountryId FROM countries WHERE CountryId IN (SELECT Country FROM car_makers);	car_1
SELECT DISTINCT T2.CountryName, T2.CountryId FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId;	car_1
SELECT COUNT(*) FROM cars_data WHERE Horsepower > 150;	car_1
SELECT COUNT(*) FROM cars_data WHERE Horsepower > 150;	car_1
SELECT Year, AVG(Weight) FROM cars_data GROUP BY Year;	car_1
SELECT Year, AVG(Weight) FROM cars_data GROUP BY Year;	car_1
SELECT T2.CountryName FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId JOIN continents AS T3 ON T2.Continent = T3.ContId WHERE T3.Continent = 'europe' GROUP BY T2.CountryName HAVING COUNT(T1.Id) >= 3;	car_1
SELECT T2.CountryName FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId JOIN continents AS T3 ON T2.Continent = T3.ContId WHERE T3.Continent = 'europe' GROUP BY T2.CountryName HAVING COUNT(T1.Id) >= 3;	car_1
SELECT MAX(c.Horsepower), cn.Make FROM cars_data c JOIN car_names cn ON c.Id = cn.MakeId WHERE c.Cylinders = 3;	car_1
SELECT T1.Horsepower, T2.Make FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T1.Cylinders = 3 ORDER BY T1.Horsepower DESC LIMIT 1;	car_1
SELECT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.ModelId = T2.Id ORDER BY T2.MPG DESC LIMIT 1;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id ORDER BY T2.MPG DESC LIMIT 1;	car_1
SELECT AVG(CAST(REPLACE(Horsepower, ',', '') AS REAL)) AS AverageHorsepower FROM cars_data WHERE Year < 1980;	car_1
SELECT AVG(CAST(REPLACE(Horsepower, ',', '') AS REAL)) AS AverageHorsepower FROM cars_data WHERE Year < 1980;	car_1
SELECT AVG(Edispl) FROM cars_data WHERE Id IN (SELECT MakeId FROM car_names WHERE Model IN (SELECT Model FROM model_list WHERE Maker = (SELECT Id FROM car_makers WHERE Maker = 'volvo')))	car_1
SELECT AVG(cars_data.Edispl) FROM cars_data JOIN car_names ON cars_data.Id = car_names.MakeId JOIN model_list ON car_names.Model = model_list.Model JOIN car_makers ON model_list.Maker = car_makers.Id WHERE car_makers.Maker = 'volvo';	car_1
SELECT Cylinders, MAX(Accelerate) FROM cars_data GROUP BY Cylinders;	car_1
SELECT Cylinders, MAX(Accelerate) AS MaxAccelerate FROM cars_data GROUP BY Cylinders;	car_1
SELECT Model FROM model_list GROUP BY Model ORDER BY COUNT(Maker) DESC LIMIT 1;	car_1
SELECT Model FROM model_list GROUP BY Model ORDER BY COUNT(*) DESC LIMIT 1;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 4;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 4;	car_1
SELECT COUNT(*) FROM cars_data WHERE Year = 1980;	car_1
SELECT COUNT(*) FROM cars_data WHERE Year = 1980;	car_1
SELECT COUNT(DISTINCT ml.Model) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN countries c ON cm.Country = c.CountryId JOIN continents cont ON c.Continent = cont.ContId WHERE cm.FullName = 'American Motor Company';	car_1
SELECT COUNT(DISTINCT ml.Model) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN countries c ON cm.Country = c.CountryId JOIN continents cont ON c.Continent = cont.ContId WHERE cont.Continent = 'america' AND cm.FullName = 'American Motor Company';	car_1
SELECT T1.FullName, T1.Id FROM car_makers AS T1 JOIN model_list AS T2 ON T1.Id = T2.Maker GROUP BY T1.Id HAVING COUNT(T2.Model) > 3;	car_1
SELECT T1.Maker, T1.Id FROM car_makers AS T1 JOIN model_list AS T2 ON T1.Id = T2.Maker GROUP BY T1.Id HAVING COUNT(T2.Model) > 3;	car_1
SELECT DISTINCT ml.Model FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN cars_data cd ON cm.Id = cd.Id WHERE cm.FullName = 'General Motors' OR cd.Weight > 3500;	car_1
SELECT DISTINCT cn.Model FROM car_names cn JOIN cars_data cd ON cn.MakeId = cd.Id JOIN model_list ml ON cn.Model = ml.Model JOIN car_makers cm ON ml.Maker = cm.Id WHERE cm.FullName = 'General Motors' OR cd.Weight > 3500;	car_1
SELECT DISTINCT Year FROM cars_data WHERE Weight BETWEEN 3000 AND 4000;	car_1
SELECT DISTINCT Year FROM cars_data WHERE Weight <4000 INTERSECT SELECT DISTINCT Year FROM cars_data WHERE Weight > 3000;	car_1
SELECT Horsepower FROM cars_data ORDER BY Accelerate DESC LIMIT 1;	car_1
SELECT Horsepower FROM cars_data ORDER BY Accelerate DESC LIMIT 1;	car_1
SELECT T2.Cylinders FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id JOIN model_list AS T3 ON T1.Model = T3.Model JOIN car_makers AS T4 ON T3.Maker = T4.Id WHERE T4.Maker = 'volvo' ORDER BY T2.Accelerate ASC LIMIT 1;	car_1
SELECT T3.Cylinders FROM car_makers AS T1 JOIN model_list AS T2 ON T1.Id = T2.Maker JOIN cars_data AS T3 ON T2.Model = T3.Id WHERE T1.Maker = 'volvo' ORDER BY T3.Accelerate ASC LIMIT 1;	car_1
SELECT COUNT(*) FROM cars_data WHERE Accelerate > (SELECT MAX(Horsepower) FROM cars_data);	car_1
SELECT COUNT(*) FROM cars_data WHERE Accelerate > (SELECT MAX(Horsepower) FROM cars_data);	car_1
SELECT T1.CountryName FROM countries AS T1 JOIN car_makers AS T2 ON T1.CountryId = T2.Country GROUP BY T1.CountryId HAVING COUNT(T2.Id) > 2;	car_1
SELECT COUNT(*) FROM ( SELECT Country FROM car_makers GROUP BY Country HAVING COUNT(*) > 2 ) AS SubQuery;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 6;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 6;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Cylinders = 4 ORDER BY CAST(REPLACE(T2.Horsepower, ',', '') AS REAL) DESC LIMIT 1;	car_1
SELECT T1.Model, T2.Horsepower FROM model_list AS T1 JOIN cars_data AS T2 ON T1.Model = T2.Id WHERE T2.Cylinders = 4 ORDER BY CAST(REPLACE(T2.Horsepower, ',', '') AS REAL) DESC LIMIT 1;	car_1
SELECT T1.MakeId, T1.Make FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Horsepower > (SELECT MIN(Horsepower) FROM cars_data) AND T2.Cylinders <= 3;	car_1
SELECT T1.MakeId, T1.Make FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Horsepower > (SELECT MIN(Horsepower) FROM cars_data) AND T2.Cylinders < 4;	car_1
SELECT MAX(MPG) FROM cars_data WHERE Cylinders = 8 OR Year < 1980;	car_1
SELECT MAX(MPG) FROM cars_data WHERE Cylinders = 8 OR Year < 1980;	car_1
SELECT ml.Model FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN cars_data cd ON ml.Model = cd.Id WHERE cd.Weight < 3500 AND cm.FullName != 'Ford Motor Company';	car_1
SELECT DISTINCT T1.Model FROM car_names AS T1 JOIN cars_data AS T2ON T1.MakeId = T2.Id JOIN model_list AS T3 ON T1.Model = T3.Model JOIN car_makers AS T4 ON T3.Maker = T4.Id WHERE T2.Weight <3500AND T4.Maker != 'Ford';	car_1
SELECT CountryName FROM countries WHERE CountryId NOT IN (SELECT Country FROM car_makers);	car_1
SELECT CountryName FROM countries WHERE CountryId NOT IN (SELECT Country FROM car_makers);	car_1
SELECT cm.Id, cm.Maker FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.Id, cm.Maker HAVING COUNT(ml.Model) >=2AND cm.Id IN ( SELECT Maker FROM model_list GROUP BY Maker HAVING COUNT(Model) > 3 );	car_1
SELECT T1.Id, T1.Maker FROM car_makers AS T1 JOIN model_list AS T2 ON T1.Id = T2.Maker GROUP BY T1.Id, T1.Maker HAVING COUNT(DISTINCT T2.Model) >=2 AND COUNT(T2.Model) > 3;	car_1
SELECT c.CountryId, c.CountryName FROM countries c JOIN car_makers cm ON c.CountryId = cm.Country GROUP BY c.CountryId, c.CountryName HAVING COUNT(cm.Id) >3 OR EXISTS (SELECT 1 FROM car_makers cm2 JOIN model_list ml ON cm2.Id = ml.Maker WHERE cm2.Country = c.CountryId AND ml.Model = 'fiat')	car_1
SELECT DISTINCT T1.CountryId, T1.CountryName FROM countries AS T1 JOIN car_makers AS T2 ON T1.CountryId = T2.Country WHERE T2.Maker = 'fiat' OR T1.CountryId IN ( SELECT Country FROM car_makers GROUP BY Country HAVING COUNT(*) > 3 );	car_1
SELECT Country FROM airlines WHERE Airline = "JetBlue Airways";	flight_2
SELECT Country FROM airlines WHERE Airline = 'Jetblue Airways';	flight_2
SELECT Abbreviation FROM airlines WHERE Airline = "JetBlue Airways";	flight_2
SELECT Abbreviation FROM airlines WHERE Airline = 'Jetblue Airways';	flight_2
SELECT Airline, Abbreviation FROM airlines WHERE Country = 'USA';	flight_2
SELECT Airline, Abbreviation FROM airlines WHERE Country = 'USA';	flight_2
SELECT AirportCode, AirportName FROM airports WHERE City = 'Anthony';	flight_2
SELECT AirportCode, AirportName FROM airports WHERE City = 'Anthony';	flight_2
SELECT count(*) FROM airlines;	flight_2
SELECT count(*) FROM airlines;	flight_2
SELECT COUNT(*) FROM airports;	flight_2
SELECT COUNT(*) FROM airports;	flight_2
SELECT count(*) FROM flights;	flight_2
SELECT count(*) FROM flights;	flight_2
SELECT Airline FROM airlines WHERE Abbreviation = 'UAL';	flight_2
SELECT Airline FROM airlines WHERE Abbreviation = 'UAL';	flight_2
SELECT COUNT(*) FROM airlines WHERE Country = 'USA';	flight_2
SELECT count(*) FROM airlines WHERE Country = 'USA';	flight_2
SELECT City, Country FROM airports WHERE AirportName = 'Alton';	flight_2
SELECT City, Country FROM airports WHERE AirportName = 'Alton';	flight_2
SELECT AirportName FROM airports WHERE AirportCode = 'AKO';	flight_2
SELECT AirportName FROM airports WHERE AirportCode = 'AKO';	flight_2
SELECT AirportName FROM airports WHERE City = 'Aberdeen';	flight_2
SELECT AirportName FROM airports WHERE City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = 'APG';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = 'APG';	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport = 'ATO';	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport = 'ATO';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.SourceAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.SourceAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights f JOIN airports src ON f.SourceAirport = src.AirportCode JOIN airports dest ON f.DestAirport = dest.AirportCode WHERE src.City = 'Aberdeen' AND dest.City = 'Ashley';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = (SELECT AirportCode FROM airports WHERE City = 'Aberdeen') AND DestAirport = (SELECT AirportCode FROM airports WHERE City = 'Ashley');	flight_2
SELECT COUNT(*) FROM flights AS T1 JOIN airlines AS T2 ON T1.Airline = T2.uid WHERE T2.Airline = 'JetBlue Airways';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'JetBlue Airways';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'United Airlines' AND flights.DestAirport = 'ASY';	flight_2
SELECT COUNT(*) FROM flights AS F JOIN airlines AS A ON F.Airline = A.uid JOIN airports AS AP ON F.DestAirport = AP.AirportCode WHERE A.Airline = 'United Airlines' AND AP.AirportCode = 'ASY';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'United Airlines' AND flights.SourceAirport = 'AHD';	flight_2
SELECT COUNT(*) FROM flights AS F JOIN airlines AS A ON F.Airline = A.uid WHERE A.Airline = 'United Airlines' AND F.SourceAirport = 'AHD';	flight_2
SELECT COUNT(*) FROM flights f JOIN airlines a ON f.Airline = a.uid JOIN airports ap ON f.DestAirport = ap.AirportCode WHERE a.Airline = 'United Airlines' AND ap.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights f JOIN airlines a ON f.Airline = a.uid JOIN airports ap ON f.DestAirport = ap.AirportCode WHERE a.Airline = 'United Airlines' AND ap.City = 'Aberdeen';	flight_2
SELECT t2.City FROM flights AS t1 JOIN airports AS t2 ON t1.DestAirport = t2.AirportCode GROUP BY t2.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.City FROM airports AS T1 JOIN flights AS T2 ON T1.AirportCode = T2.DestAirport GROUP BY T1.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT t2.City FROM flights AS t1 JOIN airports AS t2 ON t1.SourceAirport = t2.AirportCode GROUP BY t2.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.City FROM airports AS T1 JOIN flights AS T2 ON T1.AirportCode = T2.SourceAirport GROUP BY T1.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT SourceAirport FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.Abbreviation, T1.Country FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.uid ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT T1.Abbreviation, T1.Country FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Abbreviation, T1.Country ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.DestAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.DestAirport = 'AHD';	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' INTERSECT SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO';	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' INTERSECT SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO' AND T1.uid NOT IN ( SELECT T1.uid FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' );	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO' AND T1.uid NOT IN ( SELECT T1.uid FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' );	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) >= 10;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) >= 10;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) < 200;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) < 200;	flight_2
SELECT T1.FlightNo FROM flights AS T1 JOIN airlines AS T2 ON T1.Airline = T2.uid WHERE T2.Airline = "United Airlines";	flight_2
SELECT FlightNo FROM flights WHERE Airline = (SELECT uid FROM airlines WHERE Airline = 'United Airlines')	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = 'APG';	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport IN (SELECT AirportCode FROM airports WHERE City = "Aberdeen")	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT FlightNo FROM flights WHERE DestAirport IN (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City IN ('Aberdeen', 'Abilene');	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport IN ( SELECT AirportCode FROM airports WHERE City IN ('Aberdeen', 'Abilene') );	flight_2
SELECT AirportName FROM airports WHERE AirportCode NOT IN (SELECT SourceAirport FROM flights UNION SELECT DestAirport FROM flights);	flight_2
SELECT AirportName FROM airports WHERE AirportCode NOT IN (SELECT SourceAirport FROM flights UNION SELECT DestAirport FROM flights);	flight_2
SELECT count(*) FROM employee;	employee_hire_evaluation
SELECT count(*) FROM employee;	employee_hire_evaluation
SELECT Name FROM employee ORDER BY Age ASC;	employee_hire_evaluation
SELECT Name FROM employee ORDER BY Age ASC;	employee_hire_evaluation
SELECT City, COUNT(*) FROM employee GROUP BY City;	employee_hire_evaluation
SELECT City, COUNT(*) FROM employee GROUP BY City;	employee_hire_evaluation
SELECT City FROM employee WHERE Age < 30 GROUP BY City HAVING COUNT(*) > 1;	employee_hire_evaluation
SELECT City FROM employee WHERE Age < 30 GROUP BY City HAVING COUNT(*) > 1;	employee_hire_evaluation
SELECT Location, COUNT(*) AS Number_of_Shops FROM shop GROUP BY Location;	employee_hire_evaluation
SELECT Location, COUNT(*) AS Number_of_Shops FROM shop GROUP BY Location;	employee_hire_evaluation
SELECT Manager_name, District FROM shop WHERE Number_products = (SELECT MAX(Number_products) FROM shop);	employee_hire_evaluation
SELECT Manager_name, District FROM shop ORDER BY Number_products DESC LIMIT 1;	employee_hire_evaluation
SELECT min(Number_products), max(Number_products) FROM shop;	employee_hire_evaluation
SELECT min(Number_products), max(Number_products) FROM shop;	employee_hire_evaluation
SELECT Name, Location, District FROM shop ORDER BY Number_products DESC;	employee_hire_evaluation
SELECT Name, Location, District FROM shop ORDER BY Number_products DESC;	employee_hire_evaluation
SELECT Name FROM shop WHERE Number_products > (SELECT AVG(Number_products) FROM shop)	employee_hire_evaluation
SELECT Name FROM shop WHERE Number_products > (SELECT AVG(Number_products) FROM shop)	employee_hire_evaluation
SELECT T1.Name FROM employee AS T1 JOIN evaluation AS T2 ON T1.Employee_ID = T2.Employee_ID GROUP BY T1.Employee_ID ORDER BY COUNT(T2.Year_awarded) DESC LIMIT 1;	employee_hire_evaluation
SELECT T2.Name FROM evaluation AS T1 JOIN employee AS T2 ON T1.Employee_ID = T2.Employee_ID GROUP BY T1.Employee_ID ORDER BY COUNT(T1.Year_awarded) DESC LIMIT 1;	employee_hire_evaluation
SELECT t1.Name FROM employee AS t1 JOIN evaluation AS t2 ON t1.Employee_ID = t2.Employee_ID ORDER BY t2.Bonus DESC LIMIT 1;	employee_hire_evaluation
SELECT T2.Name FROM evaluation AS T1 JOIN employee AS T2 ON T1.Employee_ID = T2.Employee_ID ORDER BY T1.Bonus DESC LIMIT 1;	employee_hire_evaluation
SELECT Name FROM employee WHERE Employee_ID NOT IN (SELECT Employee_ID FROM evaluation);	employee_hire_evaluation
SELECT Name FROM employee WHERE Employee_ID NOT IN (SELECT Employee_ID FROM evaluation);	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID = (SELECT Shop_ID FROM hiring GROUP BY Shop_ID ORDER BY COUNT(Employee_ID) DESC LIMIT 1)	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID = (SELECT Shop_ID FROM hiring GROUP BY Shop_ID ORDER BY COUNT(Employee_ID) DESC LIMIT 1)	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID NOT IN (SELECT Shop_ID FROM hiring);	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID NOT IN (SELECT Shop_ID FROM hiring);	employee_hire_evaluation
SELECT s.Name AS Shop_Name, COUNT(h.Employee_ID) AS Number_of_Employees FROM hiring h JOIN shop s ON h.Shop_ID = s.Shop_ID GROUP BY s.Name;	employee_hire_evaluation
SELECT s.Name, COUNT(h.Employee_ID) AS Number_of_Employees FROM shop s JOIN hiring h ON s.Shop_ID = h.Shop_ID GROUP BY s.Shop_ID, s.Name;	employee_hire_evaluation
SELECT SUM(Bonus) FROM evaluation;	employee_hire_evaluation
SELECT SUM(Bonus) FROM evaluation;	employee_hire_evaluation
SELECT Shop_ID, Employee_ID, Start_from, Is_full_time FROM hiring;	employee_hire_evaluation
SELECT Shop_ID, Employee_ID, Start_from, Is_full_time FROM hiring;	employee_hire_evaluation
SELECT District FROM shop WHERE Number_products <3000 INTERSECT SELECT District FROM shop WHERE Number_products > 10000;	employee_hire_evaluation
SELECT District FROM shop WHERE Number_products <3000 INTERSECT SELECT District FROM shop WHERE Number_products > 10000;	employee_hire_evaluation
SELECT COUNT(DISTINCT Location) FROM shop;	employee_hire_evaluation
SELECT count(DISTINCT Location) FROM shop;	employee_hire_evaluation
SELECT COUNT(*) FROM Documents;	cre_Doc_Template_Mgt
SELECT count(*) FROM Documents;	cre_Doc_Template_Mgt
SELECT Document_ID, Document_Name, Document_Description FROM Documents;	cre_Doc_Template_Mgt
SELECT document_id, document_name, document_description FROM Documents;	cre_Doc_Template_Mgt
SELECT Document_Name, Template_ID FROM Documents WHERE Document_Description LIKE '%w%';	cre_Doc_Template_Mgt
SELECT Document_Name, Template_ID FROM Documents WHERE Document_Description LIKE '%w%';	cre_Doc_Template_Mgt
SELECT Documents.Document_ID, Documents.Template_ID, Documents.Document_Description FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID JOIN Ref_Template_Types ON Templates.Template_Type_Code = Ref_Template_Types.Template_Type_Code WHERE Documents.Document_Name = 'Robbin CV';	cre_Doc_Template_Mgt
SELECT Documents.Document_ID, Documents.Template_ID, Documents.Document_Description FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID JOIN Ref_Template_Types ON Templates.Template_Type_Code = Ref_Template_Types.Template_Type_Code WHERE Documents.Document_Name = 'Robbin CV';	cre_Doc_Template_Mgt
SELECT COUNT(DISTINCT Template_ID) FROM Documents;	cre_Doc_Template_Mgt
SELECT COUNT(DISTINCT Template_ID) FROM Documents;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Documents d JOIN Templates t ON d.Template_ID = t.Template_ID WHERE t.Template_Type_Code = 'PPT';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Documents d JOIN Templates t ON d.Template_ID = t.Template_ID JOIN Ref_Template_Types rtt ON t.Template_Type_Code = rtt.Template_Type_Code WHERE rtt.Template_Type_Code = 'PP';	cre_Doc_Template_Mgt
SELECT Template_ID, COUNT(Document_ID) FROM Documents GROUP BY Template_ID;	cre_Doc_Template_Mgt
SELECT Template_ID, COUNT(Document_ID) FROM Documents GROUP BY Template_ID;	cre_Doc_Template_Mgt
SELECT Template_ID, Template_Type_Code FROM Templates WHERE Template_ID = ( SELECT Template_ID FROM Documents GROUP BY Template_ID ORDER BY COUNT(*) DESC LIMIT 1 )	cre_Doc_Template_Mgt
SELECT Template_ID, Template_Type_Code FROM Templates WHERE Template_ID = ( SELECT Template_ID FROM Documents GROUP BY Template_ID ORDER BY COUNT(*) DESC LIMIT 1 )	cre_Doc_Template_Mgt
SELECT Template_ID FROM Documents GROUP BY Template_ID HAVING COUNT(Document_ID) > 1;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Documents GROUP BY Template_ID HAVING COUNT(Document_ID) > 1;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_ID NOT IN (SELECT Template_ID FROM Documents)	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_ID NOT IN (SELECT Template_ID FROM Documents);	cre_Doc_Template_Mgt
SELECT COUNT(DISTINCT Template_ID) FROM Documents;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_ID, Version_Number, Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_ID, Version_Number, Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT DISTINCT Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT DISTINCT Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_Type_Code IN ('PP', 'PPT');	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_Type_Code IN ('PP', 'PPT');	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates WHERE Template_Type_Code = 'CV';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates WHERE Template_Type_Code = 'CV';	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates WHERE Version_Number > 5;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates WHERE Version_Number > 5;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(*) FROM Templates GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(Template_ID) FROM Templates GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code HAVING COUNT(Template_ID) < 3;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code HAVING COUNT(*) < 3;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates ORDER BY Version_Number ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates ORDER BY Version_Number ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT T.Template_Type_Code FROM Templates T JOIN Documents D ON T.Template_ID = D.Template_ID WHERE D.Document_Name = 'Data base';	cre_Doc_Template_Mgt
SELECT T.Template_Type_Code FROM Documents D JOIN Templates T ON D.Template_ID = T.Template_ID WHERE D.Document_Name = 'Data base';	cre_Doc_Template_Mgt
SELECT Documents.Document_Name FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID JOIN Ref_Template_Types ON Templates.Template_Type_Code = Ref_Template_Types.Template_Type_Code WHERE Ref_Template_Types.Template_Type_Code = 'BK';	cre_Doc_Template_Mgt
SELECT Documents.Document_Name FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID JOIN Ref_Template_Types ON Templates.Template_Type_Code = Ref_Template_Types.Template_Type_Code WHERE Ref_Template_Types.Template_Type_Code = 'BK';	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(Document_ID) FROM Templates JOIN Documents ON Templates.Template_ID = Documents.Template_ID GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(*) FROM Templates GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates WHERE Template_ID IN (SELECT Template_ID FROM Documents) GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates WHERE Template_Type_Code NOT IN (SELECT Template_Type_Code FROM Documents);	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types WHERE Template_Type_Code NOT IN (SELECT Template_Type_Code FROM Templates)	cre_Doc_Template_Mgt
SELECT Template_Type_Code, Template_Type_Description FROM Ref_Template_Types;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, Template_Type_Description FROM Ref_Template_Types;	cre_Doc_Template_Mgt
SELECT Template_Type_Description FROM Ref_Template_Types WHERE Template_Type_Code = 'AD';	cre_Doc_Template_Mgt
SELECT Template_Type_Description FROM Ref_Template_Types WHERE Template_Type_Code = 'AD';	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types WHERE Template_Type_Description = 'Book';	cre_Doc_Template_Mgt
SELECT T1.Template_Type_Code FROM Ref_Template_Types AS T1 JOIN Templates AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code WHERE T1.Template_Type_Description = 'Book';	cre_Doc_Template_Mgt
SELECT DISTINCT T3.Template_Type_Description FROM Documents AS T1 JOIN Templates AS T2 ON T1.Template_ID = T2.Template_ID JOIN Ref_Template_Types AS T3 ON T2.Template_Type_Code = T3.Template_Type_Code;	cre_Doc_Template_Mgt
SELECT DISTINCT T1.Document_Description FROM Documents AS T1 JOIN Templates AS T2 ON T1.Template_ID = T2.Template_ID;	cre_Doc_Template_Mgt
SELECT T1.Template_ID FROM Templates AS T1 JOIN Ref_Template_Types AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code WHERE T2.Template_Type_Description = 'Presentation';	cre_Doc_Template_Mgt
SELECT T1.Template_ID FROM Templates AS T1 JOIN Ref_Template_Types AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code WHERE T2.Template_Type_Description = 'Presentation';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Documents AS t1 JOIN Paragraphs AS t2 ON t1.Document_ID = t2.Document_ID WHERE t1.Document_Name = 'Summer Show';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs WHERE Document_ID = (SELECT Document_ID FROM Documents WHERE Document_Name = 'Summer Show');	cre_Doc_Template_Mgt
SELECT Other_Details FROM Paragraphs WHERE Paragraph_Text = 'Korea';	cre_Doc_Template_Mgt
SELECT Other_Details FROM Paragraphs WHERE Paragraph_Text LIKE '%Korea%';	cre_Doc_Template_Mgt
SELECT Paragraph_ID, Paragraph_Text FROM Paragraphs WHERE Document_ID = (SELECT Document_ID FROM Documents WHERE Document_Name = 'Welcome to NY');	cre_Doc_Template_Mgt
SELECT Paragraph_ID, Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Welcome to NY';	cre_Doc_Template_Mgt
SELECT Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Customer reviews';	cre_Doc_Template_Mgt
SELECT Paragraph_Text FROM Paragraphs WHERE Document_ID = (SELECT Document_ID FROM Documents WHERE Document_Name = 'Customer reviews');	cre_Doc_Template_Mgt
SELECT Documents.Document_ID, COUNT(Paragraphs.Paragraph_ID) AS Number_of_Paragraphs FROM Documents LEFT JOIN Paragraphs ON Documents.Document_ID = Paragraphs.Document_ID GROUP BY Documents.Document_ID ORDER BY Documents.Document_ID;	cre_Doc_Template_Mgt
SELECT document_id, COUNT(paragraph_id) AS number_of_paragraphs FROM Paragraphs GROUP BY document_id ORDER BY document_id;	cre_Doc_Template_Mgt
SELECT D.Document_ID, D.Document_Name, COUNT(P.Paragraph_ID) AS Number_of_Paragraphs FROM Documents D LEFT JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID, D.Document_Name;	cre_Doc_Template_Mgt
SELECT d.Document_ID, d.Document_Name, COUNT(p.Paragraph_ID) AS Number_of_Paragraphs FROM Documents d LEFT JOIN Paragraphs p ON d.Document_ID = p.Document_ID GROUP BY d.Document_ID, d.Document_Name;	cre_Doc_Template_Mgt
SELECT document_id FROM Paragraphs GROUP BY document_id HAVING COUNT(paragraph_id) >= 2;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID HAVING COUNT(*) >= 2;	cre_Doc_Template_Mgt
SELECT D.Document_ID, D.Document_Name FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID, D.Document_Name ORDER BY COUNT(P.Paragraph_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT D.Document_ID, D.Document_Name FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID ORDER BY COUNT(P.Paragraph_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID ORDER BY COUNT(*) ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID ORDER BY COUNT(*) ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT D.Document_ID FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID HAVING COUNT(P.Paragraph_ID) BETWEEN 1 AND 2;	cre_Doc_Template_Mgt
SELECT D.Document_ID FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID HAVING COUNT(P.Paragraph_ID) BETWEEN 1 AND 2;	cre_Doc_Template_Mgt
SELECT D.Document_ID FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID WHERE P.Paragraph_Text LIKE '%Brazil%' AND P.Paragraph_Text LIKE '%Ireland%';	cre_Doc_Template_Mgt
SELECT T1.document_id FROM Documents AS T1 JOIN Paragraphs AS T2 ON T1.document_id = T2.document_id WHERE T2.Paragraph_Text LIKE '%Brazil%' AND T2.Paragraph_Text LIKE '%Ireland%';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM teacher;	course_teach
SELECT COUNT(*) FROM teacher;	course_teach
SELECT Name FROM teacher ORDER BY Age ASC;	course_teach
SELECT Name FROM teacher ORDER BY Age ASC;	course_teach
SELECT Age, Hometown FROM teacher;	course_teach
SELECT Age, Hometown FROM teacher;	course_teach
SELECT Name FROM teacher WHERE Hometown != 'Little Lever Urban District';	course_teach
SELECT Name FROM teacher WHERE Hometown != 'Little Lever Urban District';	course_teach
SELECT Name FROM teacher WHERE Age = 32 OR Age = 33;	course_teach
SELECT Name FROM teacher WHERE Age = 32 OR Age = 33;	course_teach
SELECT Hometown FROM teacher ORDER BY Age ASC LIMIT 1;	course_teach
SELECT Hometown FROM teacher ORDER BY Age ASC LIMIT 1;	course_teach
SELECT Hometown, COUNT(*) FROM teacher GROUP BY Hometown;	course_teach
SELECT Hometown, COUNT(*) FROM teacher GROUP BY Hometown;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown ORDER BY COUNT(*) DESC LIMIT 1;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown ORDER BY COUNT(*) DESC LIMIT 1;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown HAVING COUNT(*) >= 2;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown HAVING COUNT(*) >= 2;	course_teach
SELECT T3.Name, T2.Course FROM course_arrange AS T1 JOIN course AS T2 ON T1.Course_ID = T2.Course_ID JOIN teacher AS T3 ON T1.Teacher_ID = T3.Teacher_ID;	course_teach
SELECT T3.Name, T2.Course FROM course_arrange AS T1 JOIN course AS T2 ON T1.Course_ID = T2.Course_ID JOIN teacher AS T3 ON T1.Teacher_ID = T3.Teacher_ID;	course_teach
SELECT T.Name, C.Course FROM teacher AS T JOIN course_arrange AS CA ON T.Teacher_ID = CA.Teacher_ID JOIN course AS C ON CA.Course_ID = C.Course_ID ORDER BY T.Name ASC;	course_teach
SELECT T.Name, C.Course FROM teacher AS T JOIN course_arrange AS CA ON T.Teacher_ID = CA.Teacher_ID JOIN course AS C ON CA.Course_ID = C.Course_ID ORDER BY T.Name ASC;	course_teach
SELECT T3.Name FROM course AS T1 JOIN course_arrange AS T2 ON T1.Course_ID = T2.Course_ID JOIN teacher AS T3 ON T2.Teacher_ID = T3.Teacher_ID WHERE T1.Course = 'Math';	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID JOIN course AS T3 ON T1.Course_ID = T3.Course_ID WHERE T3.Course = 'Math';	course_teach
SELECT T2.Name, COUNT(T1.Course_ID) FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T2.Name;	course_teach
SELECT T2.Name, COUNT(T1.Course_ID) AS Course_Count FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T2.Name;	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T1.Teacher_ID HAVING COUNT(DISTINCT T1.Course_ID) >= 2;	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T1.Teacher_ID HAVING COUNT(DISTINCT T1.Course_ID) >= 2;	course_teach
SELECT Name FROM teacher WHERE Teacher_ID NOT IN (SELECT Teacher_ID FROM course_arrange)	course_teach
SELECT Name FROM teacher WHERE Teacher_ID NOT IN (SELECT Teacher_ID FROM course_arrange)	course_teach
SELECT COUNT(*) FROM visitor WHERE Age < 30;	museum_visit
SELECT Name FROM visitor WHERE Level_of_membership > 4 ORDER BY Level_of_membership DESC;	museum_visit
SELECT AVG(Age) FROM visitor WHERE Level_of_membership <= 4;	museum_visit
SELECT Name, Level_of_membership FROM visitor WHERE Level_of_membership > 4 ORDER BY Age DESC;	museum_visit
SELECT Museum_ID, Name FROM museum ORDER BY Num_of_Staff DESC LIMIT 1;	museum_visit
SELECT AVG(Num_of_Staff) FROM museum WHERE Open_Year < 2009;	museum_visit
SELECT Num_of_Staff, Open_Year FROM museum WHERE Name = 'Plaza Museum';	museum_visit
SELECT Name FROM museum WHERE Num_of_Staff > (SELECT MIN(Num_of_Staff) FROM museum WHERE Open_Year > 2010)	museum_visit
SELECT v.ID, v.Name, v.Age FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID GROUP BY v.ID HAVING COUNT(vi.Museum_ID) > 1;	museum_visit
SELECT v.ID, v.Name, v.Level_of_membership FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID GROUP BY v.ID, v.Name, v.Level_of_membership ORDER BY SUM(vi.Total_spent) DESC LIMIT 1;	museum_visit
SELECT T1.Museum_ID, T1.Name FROM museum AS T1 JOIN visit AS T2 ON T1.Museum_ID = T2.Museum_ID GROUP BY T1.Museum_ID ORDER BY COUNT(*) DESC LIMIT 1;	museum_visit
SELECT Name FROM museum WHERE Museum_ID NOT IN (SELECT Museum_ID FROM visit)	museum_visit
SELECT v.Name, v.Age FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID ORDER BY vi.Num_of_Ticket DESC LIMIT 1;	museum_visit
SELECT avg(Num_of_Ticket) , max(Num_of_Ticket) FROM visit;	museum_visit
SELECT SUM(Total_spent) FROM visit JOIN visitor ON visit.visitor_ID = visitor.ID WHERE visitor.Level_of_membership = 1;	museum_visit
SELECT v.Name FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID JOIN museum m ON vi.Museum_ID = m.Museum_ID WHERE m.Open_Year <2009 INTERSECT SELECT v.Name FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID JOIN museum m ON vi.Museum_ID = m.Museum_ID WHERE m.Open_Year > 2011;	museum_visit
SELECT COUNT(*) FROM visitor WHERE ID NOT IN ( SELECT visitor_ID FROM visit JOIN museum ON visit.Museum_ID = museum.Museum_ID WHERE museum.Open_Year > 2010 );	museum_visit
SELECT COUNT(*) FROM museum WHERE Open_Year > 2013 OR Open_Year < 2008;	museum_visit
SELECT COUNT(*) FROM players;	wta_1
SELECT COUNT(*) FROM players;	wta_1
SELECT COUNT(*) FROM matches;	wta_1
SELECT COUNT(*) FROM matches;	wta_1
SELECT first_name, birth_date FROM players WHERE country_code = 'USA';	wta_1
SELECT first_name, birth_date FROM players WHERE country_code = 'USA';	wta_1
SELECT AVG(loser_age) AS average_loser_age, AVG(winner_age) AS average_winner_age FROM matches;	wta_1
SELECT AVG(winner_age) AS average_winner_age, AVG(loser_age) AS average_loser_age FROM matches;	wta_1
SELECT AVG(winner_rank) FROM matches;	wta_1
SELECT AVG(winner_rank) AS average_winner_rank FROM matches;	wta_1
SELECT MAX(loser_rank) FROM matches;	wta_1
SELECT MIN(T2.ranking) AS best_rank FROM matches AS T1 JOIN rankings AS T2 ON T1.loser_id = T2.player_id;	wta_1
SELECT COUNT(DISTINCT country_code) FROM players;	wta_1
SELECT COUNT(DISTINCT country_code) FROM players;	wta_1
SELECT COUNT(DISTINCT loser_name) FROM matches;	wta_1
SELECT COUNT(DISTINCT loser_name) FROM matches;	wta_1
SELECT tourney_name FROM matches GROUP BY tourney_name HAVING COUNT(*) > 10;	wta_1
SELECT tourney_name FROM matches GROUP BY tourney_name HAVING COUNT(*) > 10;	wta_1
SELECT DISTINCT winner_name FROM matches WHERE year =2013 INTERSECT SELECT DISTINCT winner_name FROM matches WHERE year = 2016;	wta_1
SELECT DISTINCT p.first_name, p.last_name FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.year = 2013 INTERSECT SELECT DISTINCT p.first_name, p.last_name FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.year = 2016;	wta_1
SELECT COUNT(*) FROM matches WHERE year IN (2013, 2016);	wta_1
SELECT COUNT(*) FROM matches WHERE year IN (2013, 2016);	wta_1
SELECT DISTINCT p.country_code, p.first_name FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE (m.tourney_name = 'WTA Championships' OR m.tourney_name = 'Australian Open') GROUP BY p.player_id HAVING COUNT(DISTINCT m.tourney_name) = 2;	wta_1
SELECT DISTINCT p.first_name, p.country_code FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.tourney_level = 'W' AND m.tourney_name = 'Australian Open';	wta_1
SELECT first_name, country_code FROM players ORDER BY birth_date ASC LIMIT 1;	wta_1
SELECT first_name, country_code FROM players ORDER BY birth_date ASC LIMIT 1;	wta_1
SELECT first_name, last_name FROM players WHERE hand = 'L' ORDER BY birth_date;	wta_1
SELECT first_name, last_name FROM players WHERE hand = 'L' ORDER BY birth_date;	wta_1
SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN ( SELECT player_id, MAX(tours) AS max_tours FROM rankings GROUP BY player_id ) AS T2 ON T1.player_id = T2.player_id WHERE T2.max_tours = ( SELECT MAX(tours) FROM rankings );	wta_1
SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN ( SELECT player_id, SUM(tours) AS total_tours FROM rankings GROUP BY player_id ORDER BY total_tours DESC LIMIT1 ) AS T2 ON T1.player_id = T2.player_id;	wta_1
SELECT year FROM matches GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT year FROM matches GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.last_name, T3.ranking_points FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id JOIN rankings AS T3 ON T1.player_id = T3.player_id GROUP BY T2.winner_id ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.last_name, T2.ranking_points FROM players AS T1 JOIN rankings AS T2 ON T1.player_id = T2.player_id WHERE T1.player_id = ( SELECT winner_id FROM matches GROUP BY winner_id ORDER BY COUNT(*) DESC LIMIT 1 ) ORDER BY T2.ranking_points DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.last_name FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id WHERE T2.tourney_name = 'Australian Open' ORDER BY T2.winner_rank_points DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.last_name FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id WHERE T2.tourney_name = 'Australian Open' ORDER BY T2.winner_rank_points DESC LIMIT 1;	wta_1
SELECT m.loser_name, m.winner_name FROM matches m ORDER BY m.minutes DESC LIMIT 1;	wta_1
SELECT m.winner_name, m.loser_name FROM matches m ORDER BY m.minutes DESC LIMIT 1;	wta_1
SELECT p.first_name, AVG(r.ranking) AS average_ranking FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.player_id, p.first_name;	wta_1
SELECT p.first_name, AVG(r.ranking) AS average_ranking FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.first_name;	wta_1
SELECT p.first_name, SUM(r.ranking_points) AS total_ranking_points FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.player_id, p.first_name;	wta_1
SELECT p.first_name, SUM(r.ranking_points) AS total_ranking_points FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.player_id, p.first_name;	wta_1
SELECT country_code, COUNT(*) FROM players GROUP BY country_code;	wta_1
SELECT country_code, COUNT(*) FROM players GROUP BY country_code;	wta_1
SELECT country_code FROM players GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT country_code FROM players GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT country_code FROM players GROUP BY country_code HAVING COUNT(*) > 50;	wta_1
SELECT country_code FROM players GROUP BY country_code HAVING COUNT(*) > 50;	wta_1
SELECT ranking_date, COUNT(tours) AS total_tours FROM rankings GROUP BY ranking_date;	wta_1
SELECT ranking_date, SUM(tours) AS total_tours FROM rankings GROUP BY ranking_date;	wta_1
SELECT COUNT(*) AS number_of_matches, year FROM matches GROUP BY year;	wta_1
SELECT year, COUNT(*) AS number_of_matches FROM matches GROUP BY year;	wta_1
SELECT T1.first_name, T1.last_name, T2.ranking FROM players AS T1 JOIN rankings AS T2 ON T1.player_id = T2.player_id WHERE T1.player_id IN ( SELECT winner_id FROM matches GROUP BY winner_id ORDER BY MIN(winner_age) ASC LIMIT 3 ) ORDER BY T2.ranking ASC;	wta_1
SELECT p.first_name, p.last_name, r.ranking FROM players p JOIN matches m ON p.player_id = m.winner_id JOIN rankings r ON p.player_id = r.player_id WHERE m.tourney_date = ( SELECT MAX(tourney_date) FROM matches WHERE winner_id = p.player_id ) GROUP BY p.player_id ORDER BY p.birth_date ASC LIMIT 3;	wta_1
SELECT COUNT(DISTINCT winner_id) FROM matches JOIN players ON matches.winner_id = players.player_id WHERE tourney_name LIKE '%WTA Championships%' AND players.hand = 'L';	wta_1
SELECT COUNT(DISTINCT p.player_id) FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE p.hand = 'L';	wta_1
SELECT p.first_name, p.country_code, p.birth_date FROM players p JOIN ( SELECT player_id, SUM(ranking_points) AS total_rank_points FROM rankings GROUP BY player_id ) r ON p.player_id = r.player_id ORDER BY r.total_rank_points DESC LIMIT 1;	wta_1
SELECT p.first_name, p.country_code, p.birth_date FROM players p JOIN ( SELECT winner_id, SUM(winner_rank_points) AS total_points FROM matches GROUP BY winner_id ) m ON p.player_id = m.winner_id ORDER BY m.total_points DESC LIMIT 1;	wta_1
SELECT hand, COUNT(*) FROM players GROUP BY hand;	wta_1
SELECT hand, COUNT(*) FROM players GROUP BY hand;	wta_1
SELECT COUNT(*) FROM ship WHERE tonnage = 't';	battle_death
SELECT name, tonnage FROM ship ORDER BY name DESC;	battle_death
SELECT name, date, result FROM battle;	battle_death
SELECT MAX(killed) AS max_death_toll, MIN(killed) AS min_death_toll FROM death;	battle_death
SELECT AVG(injured) FROM death;	battle_death
SELECT killed, injured FROM death WHERE caused_by_ship_id IN (SELECT id FROM ship WHERE tonnage = 't');	battle_death
SELECT T1.name, T1.result FROM battle AS T1 WHERE T1.bulgarian_commander != 'Boril';	battle_death
SELECT DISTINCT T3.id, T3.name FROM ship AS T1 JOIN death AS T2 ON T1.id = T2.caused_by_ship_id JOIN battle AS T3 ON T1.lost_in_battle = T3.id WHERE T1.ship_type = 'Brig';	battle_death
SELECT b.id, b.name FROM battle b JOIN ship s ON b.id = s.lost_in_battle JOIN death d ON s.id = d.caused_by_ship_id GROUP BY b.id, b.name HAVING SUM(d.killed) > 10;	battle_death
SELECT T1.id, T1.name FROM ship AS T1 JOIN death AS T2 ON T1.id = T2.caused_by_ship_id GROUP BY T1.id, T1.name ORDER BY SUM(T2.injured) DESC LIMIT 1;	battle_death
SELECT DISTINCT name FROM battle WHERE bulgarian_commander = 'Kaloyan' AND latin_commander = 'Baldwin I';	battle_death
SELECT COUNT(DISTINCT result) FROM battle;	battle_death
SELECT COUNT(*) FROM battle WHERE id NOT IN ( SELECT lost_in_battle FROM ship WHERE tonnage = '225' );	battle_death
SELECT b.name, b.date FROM battle b JOIN ship s ON b.id = s.lost_in_battle WHERE s.name IN ('Lettice', 'HMS Atalanta') GROUP BY b.name, b.date HAVING COUNT(DISTINCT s.name) = 2;	battle_death
SELECT b.name, b.result, b.bulgarian_commander FROM battle b LEFT JOIN ship s ON b.id = s.lost_in_battle WHERE s.id IS NULL AND s.location = 'English Channel';	battle_death
SELECT note FROM death WHERE note LIKE '%East%';	battle_death
SELECT line_1, line_2 FROM Addresses;	student_transcripts_tracking
SELECT line_1, line_2 FROM Addresses;	student_transcripts_tracking
SELECT count(*) FROM Courses;	student_transcripts_tracking
SELECT count(*) FROM Courses;	student_transcripts_tracking
SELECT course_description FROM Courses WHERE course_name = 'math';	student_transcripts_tracking
SELECT course_description FROM Courses WHERE course_name LIKE '%math%';	student_transcripts_tracking
SELECT zip_postcode FROM Addresses WHERE city = 'Port Chelsea';	student_transcripts_tracking
SELECT zip_postcode FROM Addresses WHERE city = 'Port Chelsea';	student_transcripts_tracking
SELECT D.department_name, D.department_id FROM Departments D JOIN Degree_Programs DP ON D.department_id = DP.department_id GROUP BY D.department_id, D.department_name ORDER BY COUNT(DP.degree_program_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.department_name, T1.department_id FROM Departments AS T1 JOIN Degree_Programs AS T2 ON T1.department_id = T2.department_id GROUP BY T1.department_id ORDER BY COUNT(*) DESC LIMIT 1;	student_transcripts_tracking
SELECT COUNT(DISTINCT d.department_name) FROM Departments d JOIN Degree_Programs dp ON d.department_id = dp.department_id;	student_transcripts_tracking
SELECT COUNT(DISTINCT d.department_name) FROM Departments d JOIN Degree_Programs dp ON d.department_id = dp.department_id;	student_transcripts_tracking
SELECT COUNT(DISTINCT degree_summary_name) FROM Degree_Programs;	student_transcripts_tracking
SELECT COUNT(DISTINCT degree_program_id) FROM Degree_Programs;	student_transcripts_tracking
SELECT COUNT(DISTINCT dp.degree_program_id) FROM Degree_Programs dp JOIN Departments d ON dp.department_id = d.department_id WHERE d.department_name = 'Engineering';	student_transcripts_tracking
SELECT COUNT(DISTINCT dp.degree_program_id) FROM Degree_Programs dp JOIN Departments d ON dp.department_id = d.department_id WHERE d.department_name = 'Engineering';	student_transcripts_tracking
SELECT section_name, section_description FROM Sections;	student_transcripts_tracking
SELECT Sections.section_name, Sections.section_description FROM Sections;	student_transcripts_tracking
SELECT c.course_name, c.course_id FROM Courses c JOIN Sections s ON c.course_id = s.course_id GROUP BY c.course_id HAVING COUNT(s.section_id) <= 2;	student_transcripts_tracking
SELECT c.course_name, c.course_id FROM Courses c LEFT JOIN Sections s ON c.course_id = s.course_id GROUP BY c.course_id HAVING COUNT(s.section_id) < 2;	student_transcripts_tracking
SELECT section_name FROM Sections ORDER BY section_name DESC;	student_transcripts_tracking
SELECT section_name FROM Sections ORDER BY section_name DESC;	student_transcripts_tracking
SELECT S.semester_id, S.semester_name FROM Semesters S JOIN Student_Enrolment SE ON S.semester_id = SE.semester_id GROUP BY S.semester_id, S.semester_name ORDER BY COUNT(SE.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT S.semester_id, S.semester_name FROM Semesters S JOIN Student_Enrolment SE ON S.semester_id = SE.semester_id GROUP BY S.semester_id, S.semester_name ORDER BY COUNT(SE.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT Departments.department_description FROM Departments WHERE Departments.department_name LIKE '%the computer%';	student_transcripts_tracking
SELECT T1.department_description FROM Departments AS T1 JOIN Degree_Programs AS T2 ON T1.department_id = T2.department_id JOIN Courses AS T3 ON T2.degree_program_id = T3.course_id WHERE T3.course_description LIKE '%computer%';	student_transcripts_tracking
SELECT S.first_name, S.middle_name, S.last_name, S.student_id FROM Students S JOIN Student_Enrolment SE ON S.student_id = SE.student_id GROUP BY S.student_id HAVING COUNT(DISTINCT SE.degree_program_id) = 2;	student_transcripts_tracking
SELECT T3.first_name, T3.middle_name, T3.last_name, T3.student_id FROM Student_Enrolment_Courses AS T1 JOIN Student_Enrolment AS T2 ON T1.student_enrolment_id = T2.student_enrolment_id JOIN Students AS T3 ON T2.student_id = T3.student_id GROUP BY T3.student_id, T2.semester_id HAVING COUNT(DISTINCT T2.degree_program_id) = 2;	student_transcripts_tracking
SELECT S.first_name, S.middle_name, S.last_name FROM Students S JOIN Student_Enrolment SE ON S.student_id = SE.student_id JOIN Degree_Programs DP ON SE.degree_program_id = DP.degree_program_id;	student_transcripts_tracking
SELECT T3.first_name, T3.middle_name, T3.last_name FROM Student_Enrolment AS T1 JOIN Degree_Programs AS T2 ON T1.degree_program_id = T2.degree_program_id JOIN Students AS T3 ON T1.student_id = T3.student_id WHERE T2.degree_summary_name LIKE '%Bachelors%';	student_transcripts_tracking
SELECT dp.degree_summary_name FROM Degree_Programs dp JOIN Student_Enrolment se ON dp.degree_program_id = se.degree_program_id GROUP BY dp.degree_program_id ORDER BY COUNT(se.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT dp.degree_summary_name FROM Degree_Programs dp JOIN Student_Enrolment se ON dp.degree_program_id = se.degree_program_id GROUP BY dp.degree_program_id ORDER BY COUNT(se.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT dp.degree_program_id, dp.degree_summary_name FROM Degree_Programs dp JOIN Student_Enrolment se ON dp.degree_program_id = se.degree_program_id GROUP BY dp.degree_program_id, dp.degree_summary_name ORDER BY COUNT(se.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.degree_program_id, T1.degree_summary_name FROM Degree_Programs AS T1 JOIN Student_Enrolment AS T2 ON T1.degree_program_id = T2.degree_program_id GROUP BY T1.degree_program_id, T1.degree_summary_name ORDER BY COUNT(T2.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.student_id, T2.first_name, T2.middle_name, T2.last_name, COUNT(T1.student_enrolment_id) AS number_of_enrollments FROM Student_Enrolment AS T1 JOIN Students AS T2 ON T1.student_id = T2.student_id GROUP BY T1.student_id ORDER BY number_of_enrollments DESC LIMIT 1;	student_transcripts_tracking
SELECT T2.first_name, T2.middle_name, T2.last_name, T1.student_id, COUNT(*) as number_of_enrollments FROM Student_Enrolment AS T1 JOIN Students AS T2 ON T1.student_id = T2.student_id GROUP BY T1.student_id ORDER BY number_of_enrollments DESC LIMIT 1;	student_transcripts_tracking
SELECT semester_name FROM Semesters WHERE semester_id NOT IN (SELECT semester_id FROM Student_Enrolment);	student_transcripts_tracking
SELECT semester_name FROM Semesters WHERE semester_id NOT IN (SELECT semester_id FROM Student_Enrolment);	student_transcripts_tracking
SELECT DISTINCT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id;	student_transcripts_tracking
SELECT DISTINCT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id;	student_transcripts_tracking
SELECT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id GROUP BY T1.course_id ORDER BY count(*) DESC LIMIT 1;	student_transcripts_tracking
SELECT c.course_name FROM Courses c JOIN Student_Enrolment_Courses sec ON c.course_id = sec.course_id GROUP BY c.course_id ORDER BY COUNT(sec.student_enrolment_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT s.last_name FROM Students s JOIN Addresses a ON s.current_address_id = a.address_id WHERE a.state_province_county = 'North Carolina' AND s.student_id NOT IN (SELECT se.student_id FROM Student_Enrolment se)	student_transcripts_tracking
SELECT DISTINCT s.last_name FROM Students s JOIN Addresses a ON s.current_address_id = a.address_id LEFT JOIN Student_Enrolment se ON s.student_id = se.student_id WHERE a.state_province_county = 'North Carolina' AND se.student_enrolment_id IS NULL;	student_transcripts_tracking
SELECT T1.transcript_date, T1.transcript_id FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id GROUP BY T1.transcript_id HAVING COUNT(T2.student_course_id) >= 2;	student_transcripts_tracking
SELECT T.transcript_date, T.transcript_id FROM Transcripts T JOIN Transcript_Contents TC ON T.transcript_id = TC.transcript_id GROUP BY T.transcript_id HAVING COUNT(DISTINCT TC.student_course_id) >= 2;	student_transcripts_tracking
SELECT cell_mobile_number FROM Students WHERE first_name = 'Timmothy' AND last_name = 'Ward';	student_transcripts_tracking
SELECT T1.cell_mobile_number FROM Students AS T1 WHERE T1.first_name = 'Timmothy' AND T1.last_name = 'Ward';	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_left ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1;	student_transcripts_tracking
SELECT T2.first_name FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.permanent_address_id JOIN Addresses AS T3 ON T3.address_id = T2.current_address_id WHERE T1.address_id <> T3.address_id;	student_transcripts_tracking
SELECT DISTINCT s.first_name FROM Students s JOIN Addresses a1 ON s.permanent_address_id = a1.address_id JOIN Addresses a2 ON s.current_address_id = a2.address_id WHERE a1.address_id <> a2.address_id;	student_transcripts_tracking
SELECT T1.address_id, T1.line_1, T1.line_2, T1.line_3 FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.current_address_id GROUP BY T1.address_id ORDER BY COUNT(T2.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.address_id, T1.line_1, T1.line_2 FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.current_address_id GROUP BY T1.address_id ORDER BY COUNT(T2.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT AVG(transcript_date) FROM Transcripts;	student_transcripts_tracking
SELECT AVG(transcript_date) FROM Transcripts;	student_transcripts_tracking
SELECT T1.transcript_date, T1.other_details FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id ORDER BY T1.transcript_date ASC LIMIT 1;	student_transcripts_tracking
SELECT T.transcript_date, C.course_name, C.course_description FROM Transcripts AS T JOIN Transcript_Contents AS TC ON T.transcript_id = TC.transcript_id JOIN Student_Enrolment_Courses AS SEC ON TC.student_course_id = SEC.student_course_id JOIN Courses AS C ON SEC.course_id = C.course_id ORDER BY T.transcript_date ASC LIMIT 1;	student_transcripts_tracking
SELECT COUNT(*) FROM Transcripts WHERE transcript_date IS NOT NULL;	student_transcripts_tracking
SELECT COUNT(*) FROM Transcripts;	student_transcripts_tracking
SELECT transcript_date FROM Transcripts ORDER BY transcript_date DESC LIMIT 1;	student_transcripts_tracking
SELECT transcript_date FROM Transcripts ORDER BY transcript_date DESC LIMIT 1;	student_transcripts_tracking
SELECT student_course_id, COUNT(transcript_id) as count FROM Transcript_Contents GROUP BY student_course_id ORDER BY count DESC LIMIT 1;	student_transcripts_tracking
SELECT T3.course_id, T1.student_enrolment_id, COUNT(DISTINCT T4.transcript_id) as transcript_count FROM Student_Enrolment_Courses AS T1 JOIN Student_Enrolment AS T2 ON T1.student_enrolment_id = T2.student_enrolment_id JOIN Courses AS T3 ON T1.course_id = T3.course_id JOIN Transcript_Contents AS T4 ON T1.student_course_id = T4.student_course_id GROUP BY T3.course_id, T1.student_enrolment_id ORDER BY transcript_count DESC LIMIT 1;	student_transcripts_tracking
SELECT T.transcript_date, T.transcript_id FROM Transcripts T JOIN Transcript_Contents TC ON T.transcript_id = TC.transcript_id GROUP BY T.transcript_id ORDER BY COUNT(TC.student_course_id) ASC LIMIT 1;	student_transcripts_tracking
SELECT T1.transcript_date, T1.transcript_id FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id GROUP BY T1.transcript_id ORDER BY COUNT(T2.student_course_id) ASC LIMIT 1;	student_transcripts_tracking
SELECT DISTINCT s.semester_name FROM Semesters s JOIN Student_Enrolment se ON s.semester_id = se.semester_id JOIN Degree_Programs dp ON se.degree_program_id = dp.degree_program_id WHERE dp.degree_summary_name IN ('Master', 'Bachelor');	student_transcripts_tracking
SELECT T1.semester_id FROM Semesters AS T1 JOIN Student_Enrolment AS T2 ON T1.semester_id = T2.semester_id JOIN Degree_Programs AS T5 ON T2.degree_program_id = T5.degree_program_id WHERE T5.degree_summary_name LIKE '%Masters%' OR T5.degree_summary_name LIKE '%Bachelors%' GROUP BY T1.semester_id HAVING COUNT(DISTINCT CASE WHEN T5.degree_summary_name LIKE '%Masters%' THEN 1 ELSE NULL END) > 0 AND COUNT(DISTINCT CASE WHEN T5.degree_summary_name LIKE '%Bachelors%' THEN 1 ELSE NULL END) > 0;	student_transcripts_tracking
SELECT COUNT(DISTINCT T1.current_address_id) FROM Students AS T1;	student_transcripts_tracking
SELECT DISTINCT a.line_1, a.line_2, a.line_3, a.city, a.zip_postcode, a.state_province_county, a.country FROM Students s JOIN Addresses a ON s.current_address_id = a.address_id;	student_transcripts_tracking
SELECT Students.first_name, Students.middle_name, Students.last_name, Students.cell_mobile_number, Students.email_address, Students.ssn, Students.date_first_registered, Students.date_left, Students.other_student_details FROM Students ORDER BY Students.first_name DESC, Students.middle_name DESC, Students.last_name DESC;	student_transcripts_tracking
SELECT Students.other_student_details FROM Students ORDER BY Students.last_name DESC, Students.first_name DESC;	student_transcripts_tracking
SELECT t2.section_description FROM Courses AS t1 JOIN Sections AS t2 ON t1.course_id = t2.course_id WHERE t1.course_description = 'c';	student_transcripts_tracking
SELECT t1.course_description FROM Courses AS t1 JOIN Sections AS t2 ON t1.course_id = t2.course_id WHERE t2.section_name = "h";	student_transcripts_tracking
SELECT T1.first_name FROM Students AS T1 JOIN Addresses AS T2 ON T1.permanent_address_id = T2.address_id WHERE T2.country = 'Haiti' OR T1.cell_mobile_number = '09700166582';	student_transcripts_tracking
SELECT T2.first_name FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.permanent_address_id WHERE T1.country = 'Haiti' UNION SELECT first_name FROM Students WHERE cell_mobile_number = '09700166582';	student_transcripts_tracking
SELECT Title FROM Cartoon ORDER BY Title;	tvshow
SELECT Title FROM Cartoon ORDER BY Title;	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones';	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones';	tvshow
SELECT COUNT(*) FROM Cartoon WHERE Written_by = 'Joseph Kuhr';	tvshow
SELECT COUNT(*) FROM Cartoon WHERE Written_by = 'Joseph Kuhr';	tvshow
SELECT Title, Directed_by FROM Cartoon ORDER BY Original_air_date;	tvshow
SELECT Title, Directed_by FROM Cartoon ORDER BY Original_air_date;	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones' OR Directed_by = 'Brandon Vietti';	tvshow
SELECT Title FROM Cartoon WHERE Directed_by IN ('Ben Jones', 'Brandon Vietti');	tvshow
SELECT Country, COUNT(*) AS Number_of_TV_Channels FROM TV_Channel GROUP BY Country ORDER BY Number_of_TV_Channels DESC LIMIT 1;	tvshow
SELECT Country, COUNT(*) AS Channel_Count FROM TV_Channel GROUP BY Country ORDER BY Channel_Count DESC LIMIT 1;	tvshow
SELECT COUNT(DISTINCT series_name), COUNT(DISTINCT Content) FROM TV_Channel;	tvshow
SELECT COUNT(DISTINCT series_name), COUNT(DISTINCT Content) FROM TV_Channel;	tvshow
SELECT Content FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Content FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Package_Option FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Package_Option FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT COUNT(*) FROM TV_Channel WHERE Language = 'English';	tvshow
SELECT COUNT(*) FROM TV_Channel WHERE Language = 'English';	tvshow
SELECT Language, COUNT(*) AS Number_of_TV_Channels FROM TV_Channel GROUP BY Language ORDER BY Number_of_TV_Channels ASC LIMIT 1;	tvshow
SELECT Language, COUNT(*) AS Channel_Count FROM TV_Channel GROUP BY Language ORDER BY Channel_Count ASC LIMIT 1;	tvshow
SELECT Language, COUNT(*) FROM TV_Channel GROUP BY Language;	tvshow
SELECT Language, COUNT(*) FROM TV_Channel GROUP BY Language;	tvshow
SELECT T1.series_name FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Title = 'The Rise of the Blue Beetle!';	tvshow
SELECT T1.series_name FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Title = 'The Rise of the Blue Beetle!';	tvshow
SELECT C.Title FROM Cartoon AS C JOIN TV_Channel AS T ON C.Channel = T.id WHERE T.series_name = 'Sky Radio';	tvshow
SELECT C.Title FROM Cartoon AS C JOIN TV_Channel AS TC ON C.Channel = TC.id WHERE TC.series_name = 'Sky Radio';	tvshow
SELECT Episode FROM TV_series ORDER BY Rating;	tvshow
SELECT Episode FROM TV_series ORDER BY Rating;	tvshow
SELECT Episode, Rating FROM TV_series ORDER BY Rating DESC LIMIT 3;	tvshow
SELECT Episode, Rating FROM TV_series ORDER BY Rating DESC LIMIT 3;	tvshow
SELECT min(Share) , max(Share) FROM TV_series;	tvshow
SELECT max(Share) , min(Share) FROM TV_series;	tvshow
SELECT Air_Date FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT Air_Date FROM TV_series WHERE Episode = "A Love of a Lifetime";	tvshow
SELECT Weekly_Rank FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT Weekly_Rank FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT T3.series_name FROM TV_series AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Episode = 'A Love of a Lifetime';	tvshow
SELECT T2.series_name FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T1.Episode = 'A Love of a Lifetime';	tvshow
SELECT T1.Episode FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T2.series_name = 'Sky Radio';	tvshow
SELECT T1.Episode FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T2.series_name = 'Sky Radio';	tvshow
SELECT directed_by, COUNT(*) FROM Cartoon GROUP BY directed_by;	tvshow
SELECT Directed_by, COUNT(*) FROM Cartoon GROUP BY Directed_by;	tvshow
SELECT Production_code, Channel FROM Cartoon ORDER BY Original_air_date DESC LIMIT 1;	tvshow
SELECT Production_code, Channel FROM Cartoon ORDER BY Original_air_date DESC LIMIT 1;	tvshow
SELECT Package_Option, series_name FROM TV_Channel WHERE Hight_definition_TV = 'Yes';	tvshow
SELECT Package_Option, series_name FROM TV_Channel WHERE Hight_definition_TV = 'Yes';	tvshow
SELECT DISTINCT T1.Country FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Written_by = 'Todd Casey';	tvshow
SELECT DISTINCT T1.Country FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Written_by = 'Todd Casey';	tvshow
SELECT Country FROM TV_Channel WHERE id NOT IN ( SELECT Channel FROM Cartoon WHERE Written_by = 'Todd Casey' );	tvshow
SELECT DISTINCT T1.Country FROM TV_Channel AS T1 LEFT JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Written_by != 'Todd Casey' OR T2.Written_by IS NULL;	tvshow
SELECT T1.series_name, T1.Country FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Directed_by IN ('Ben Jones', 'Michael Chang');	tvshow
SELECT DISTINCT T1.series_name, T1.Country FROM TV_Channel AS T1 JOIN Cartoon AS T2 ON T1.id = T2.Channel WHERE T2.Directed_by IN ('Ben Jones', 'Michael Chang');	tvshow
SELECT Pixel_aspect_ratio_PAR, Country FROM TV_Channel WHERE Language != 'English';	tvshow
SELECT Pixel_aspect_ratio_PAR, Country FROM TV_Channel WHERE Language != 'English';	tvshow
SELECT T1.id FROM TV_Channel AS T1 JOIN TV_series AS T2 ON T1.id = T2.Channel GROUP BY T1.id HAVING COUNT(T1.id) > 2;	tvshow
SELECT id FROM TV_Channel GROUP BY id HAVING COUNT(*) > 2;	tvshow
SELECT id FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones')	tvshow
SELECT id FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones')	tvshow
SELECT Package_Option FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones');	tvshow
SELECT Package_Option FROM TV_Channel WHERE id NOT IN ( SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones' );	tvshow
SELECT count(*) FROM poker_player;	poker_player
SELECT COUNT(*) FROM poker_player;	poker_player
SELECT Earnings FROM poker_player ORDER BY Earnings DESC;	poker_player
SELECT Earnings FROM poker_player ORDER BY Earnings DESC;	poker_player
SELECT Final_Table_Made, Best_Finish FROM poker_player;	poker_player
SELECT Final_Table_Made, Best_Finish FROM poker_player;	poker_player
SELECT AVG(Earnings) FROM poker_player;	poker_player
SELECT AVG(Earnings) FROM poker_player;	poker_player
SELECT Money_Rank FROM poker_player ORDER BY Earnings DESC LIMIT 1;	poker_player
SELECT Money_Rank FROM poker_player ORDER BY Earnings DESC LIMIT 1;	poker_player
SELECT MAX(Final_Table_Made) FROM poker_player WHERE Earnings < 200000;	poker_player
SELECT max(Final_Table_Made) FROM poker_player WHERE Earnings < 200000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID WHERE T1.Earnings > 300000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID WHERE T1.Earnings > 300000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Final_Table_Made ASC;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Final_Table_Made ASC;	poker_player
SELECT T2.Birth_Date FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings ASC LIMIT 1;	poker_player
SELECT T2.Birth_Date FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings ASC LIMIT 1;	poker_player
SELECT T1.Money_Rank FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T2.Height DESC LIMIT 1;	poker_player
SELECT T1.Money_Rank FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T2.Height DESC LIMIT 1;	poker_player
SELECT AVG(Earnings) FROM poker_player JOIN people ON poker_player.People_ID = people.People_ID WHERE people.Height > 200;	poker_player
SELECT AVG(Earnings) FROM poker_player JOIN people ON poker_player.People_ID = people.People_ID WHERE people.Height > 200;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings DESC;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings DESC;	poker_player
SELECT Nationality, COUNT(*) FROM people GROUP BY Nationality;	poker_player
SELECT Nationality, COUNT(*) FROM people GROUP BY Nationality;	poker_player
SELECT Nationality FROM people GROUP BY Nationality ORDER BY COUNT(*) DESC LIMIT 1;	poker_player
SELECT Nationality FROM people GROUP BY Nationality ORDER BY COUNT(*) DESC LIMIT 1;	poker_player
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*) >= 2;	poker_player
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*) >= 2;	poker_player
SELECT Name, Birth_Date FROM people ORDER BY Name ASC;	poker_player
SELECT Name, Birth_Date FROM people ORDER BY Name;	poker_player
SELECT Name FROM people WHERE Nationality != 'Russia';	poker_player
SELECT Name FROM people WHERE Nationality != 'Russia';	poker_player
SELECT Name FROM people WHERE People_ID NOT IN (SELECT People_ID FROM poker_player);	poker_player
SELECT Name FROM people WHERE People_ID NOT IN (SELECT People_ID FROM poker_player);	poker_player
SELECT COUNT(DISTINCT Nationality) FROM people;	poker_player
SELECT COUNT(DISTINCT Nationality) FROM people;	poker_player
SELECT COUNT(DISTINCT state) FROM AREA_CODE_STATE;	voter_1
SELECT contestant_number, contestant_name FROM CONTESTANTS ORDER BY contestant_name DESC;	voter_1
SELECT vote_id, phone_number, state FROM VOTES;	voter_1
SELECT max(area_code), min(area_code) FROM AREA_CODE_STATE;	voter_1
SELECT MAX(created) FROM VOTES WHERE state = 'CA';	voter_1
SELECT contestant_name FROM CONTESTANTS WHERE contestant_name != 'Jessie Alloway';	voter_1
SELECT DISTINCT state, created FROM VOTES;	voter_1
SELECT C.contestant_number, C.contestant_name FROM CONTESTANTS C JOIN VOTES V ON C.contestant_number = V.contestant_number GROUP BY C.contestant_number, C.contestant_name HAVING COUNT(V.vote_id) >= 2;	voter_1
SELECT c.contestant_number, c.contestant_name FROM CONTESTANTS c JOIN VOTES v ON c.contestant_number = v.contestant_number GROUP BY c.contestant_number, c.contestant_name ORDER BY COUNT(v.vote_id) ASC LIMIT 1;	voter_1
SELECT COUNT(*) FROM VOTES WHERE state IN ('NY', 'CA');	voter_1
SELECT COUNT(*) FROM CONTESTANTS WHERE contestant_number NOT IN (SELECT contestant_number FROM VOTES);	voter_1
SELECT area_code FROM AREA_CODE_STATE WHERE state = ( SELECT state FROM VOTES GROUP BY state ORDER BY COUNT(*) DESC LIMIT 1 )	voter_1
SELECT V.created, V.state, V.phone_number FROM VOTES V JOIN CONTESTANTS C ON V.contestant_number = C.contestant_number WHERE C.contestant_name = 'Tabatha Gehling';	voter_1
SELECT DISTINCT T1.area_code FROM AREA_CODE_STATE AS T1 JOIN VOTES AS T2 ON T1.state = T2.state JOIN CONTESTANTS AS T3 ON T2.contestant_number = T3.contestant_number WHERE T3.contestant_name = 'Tabatha Gehling' INTERSECT SELECT DISTINCT T1.area_code FROM AREA_CODE_STATE AS T1 JOIN VOTES AS T2 ON T1.state = T2.state JOIN CONTESTANTS AS T3 ON T2.contestant_number = T3.contestant_number WHERE T3.contestant_name = 'Kelly Clauss';	voter_1
SELECT contestant_name FROM CONTESTANTS WHERE contestant_name LIKE '%Al%';	voter_1
SELECT Name FROM country WHERE IndepYear > 1950;	world_1
SELECT Name FROM country WHERE IndepYear > 1950;	world_1
SELECT COUNT(*) FROM country WHERE GovernmentForm = 'Republic';	world_1
SELECT COUNT(*) FROM country WHERE GovernmentForm = 'Republic';	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Region = 'Caribbean';	world_1
SELECT SUM(SurfaceArea) AS TotalSurfaceArea FROM country WHERE Code2 = 'AN';	world_1
SELECT Continent FROM country WHERE Name = 'Anguilla';	world_1
SELECT Continent FROM country WHERE Name = 'Anguilla';	world_1
SELECT T1.Region FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T2.Name = 'Kabul';	world_1
SELECT T1.Region FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T2.Name = 'Kabul';	world_1
SELECT Language FROM countrylanguage WHERE CountryCode = (SELECT Code FROM country WHERE Name = 'Aruba') ORDER BY Percentage DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage WHERE CountryCode = 'ABW' ORDER BY Percentage DESC LIMIT 1;	world_1
SELECT country.Population, country.LifeExpectancy FROM country WHERE country.Name = 'Brazil';	world_1
SELECT Population, LifeExpectancy FROM country WHERE Code = 'BRA';	world_1
SELECT T1.Region, T1.Population FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T1.Name = 'Angola';	world_1
SELECT T1.Region, T1.Population FROM country AS T1 WHERE T1.Name = 'Angola';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Region = 'Central Africa';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Continent = 'Africa' AND Region = 'Central Africa';	world_1
SELECT Name FROM country WHERE Continent = 'Asia' ORDER BY LifeExpectancy ASC LIMIT 1;	world_1
SELECT Name FROM country WHERE Continent = 'Asia' ORDER BY LifeExpectancy ASC LIMIT 1;	world_1
SELECT SUM(c.Population) AS TotalPopulation, MAX(c.GNP) AS MaxGNP FROM country c WHERE c.Continent = 'Asia';	world_1
SELECT SUM(T1.Population), MAX(T1.GNP) FROM country AS T1 WHERE T1.Continent = 'Asia';	world_1
SELECT AVG(T1.LifeExpectancy) FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T1.Continent = 'Africa' AND T1.GovernmentForm = 'Republic';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Continent = 'Africa' AND GovernmentForm = 'Republic';	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Continent IN ('Asia', 'Europe');	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Continent IN ('Asia', 'Europe');	world_1
SELECT SUM(Population) FROM city WHERE District = 'Gelderland';	world_1
SELECT SUM(Population) FROM city WHERE District = 'Gelderland';	world_1
SELECT AVG(GNP), SUM(Population) FROM country WHERE GovernmentForm = 'US Territory';	world_1
SELECT AVG(GNP), SUM(Population) FROM country WHERE Code IN (SELECT CountryCode FROM city WHERE CountryCode = 'ARE');	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage;	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage;	world_1
SELECT COUNT(DISTINCT GovernmentForm) FROM country WHERE Continent = 'Africa';	world_1
SELECT COUNT(DISTINCT T1.GovernmentForm) FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T1.Continent = 'Africa';	world_1
SELECT COUNT(*) FROM countrylanguage WHERE CountryCode = (SELECT Code FROM country WHERE Name = 'Aruba');	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage WHERE CountryCode = 'ABW';	world_1
SELECT COUNT(*) FROM countrylanguage WHERE CountryCode = 'AFG' AND IsOfficial = 'T';	world_1
SELECT COUNT(*) FROM countrylanguage WHERE CountryCode = 'AFG' AND IsOfficial = 'T';	world_1
SELECT c.Name FROM country AS c JOIN countrylanguage AS cl ON c.Code = cl.CountryCode GROUP BY c.Name ORDER BY COUNT(DISTINCT cl.Language) DESC LIMIT 1;	world_1
SELECT T1.Name FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode GROUP BY T1.Name ORDER BY COUNT(DISTINCT T2.Language) DESC LIMIT 1;	world_1
SELECT Continent FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode GROUP BY Continent ORDER BY COUNT(DISTINCT Language) DESC LIMIT 1;	world_1
SELECT Continent FROM ( SELECT Continent, COUNT(DISTINCT Language) AS LanguageCount FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode GROUP BY Continent ) AS ContinentLanguages ORDER BY LanguageCount DESC LIMIT 1;	world_1
SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'English' INTERSECT SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'Dutch';	world_1
SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'English' OR T2.Language = 'Dutch' GROUP BY T1.Code HAVING COUNT(DISTINCT T2.Language) = 2;	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl2.Language = 'French';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl2.Language = 'French';	world_1
SELECT c.Name FROM country AS c JOIN countrylanguage AS cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage AS cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl1.IsOfficial = 'T' AND cl2.Language = 'French' AND cl2.IsOfficial = 'T';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl1.IsOfficial = 'T' AND cl2.Language = 'French' AND cl2.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT T1.Continent) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'Chinese';	world_1
SELECT COUNT(DISTINCT Continent) FROM country WHERE Code IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'Chinese' );	world_1
SELECT DISTINCT T1.Region FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language IN ('English', 'Dutch');	world_1
SELECT DISTINCT T1.Region FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language IN ('Dutch', 'English');	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode WHERE (cl.Language = 'English' OR cl.Language = 'Dutch') AND cl.IsOfficial = 'T';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode WHERE (cl.Language = 'English' AND cl.IsOfficial = 'T') OR (cl.Language = 'Dutch' AND cl.IsOfficial = 'T');	world_1
SELECT cl.Language FROM countrylanguage cl JOIN country c ON cl.CountryCode = c.Code WHERE c.Continent = 'Asia' GROUP BY cl.Language ORDER BY SUM(cl.Percentage) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage WHERE CountryCode IN (SELECT Code FROM country WHERE Continent = 'Asia') GROUP BY Language ORDER BY COUNT(DISTINCT CountryCode) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage WHERE CountryCode IN ( SELECT Code FROM country WHERE GovernmentForm = 'Republic' GROUP BY Code HAVING COUNT(*) = 1 );	world_1
SELECT cl.Language FROM countrylanguage cl JOIN country c ON cl.CountryCode = c.Code WHERE c.GovernmentForm = 'Republic' GROUP BY cl.Language HAVING COUNT(DISTINCT cl.CountryCode) = 1;	world_1
SELECT c.Name FROM city c JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode WHERE cl.Language = 'English' ORDER BY c.Population DESC LIMIT 1;	world_1
SELECT c.Name FROM city c JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode WHERE cl.Language = 'English' ORDER BY c.Population DESC LIMIT 1;	world_1
SELECT T1.Name, T1.Population, T1.LifeExpectancy FROM country AS T1 WHERE T1.Continent = 'Asia' ORDER BY T1.SurfaceArea DESC LIMIT 1;	world_1
SELECT Name, Population, LifeExpectancy FROM country WHERE Continent = 'Asia' ORDER BY SurfaceArea DESC LIMIT 1;	world_1
SELECT AVG(T1.LifeExpectancy) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'English' AND T2.IsOfficial = 'F';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' AND IsOfficial = 'T' );	world_1
SELECT SUM(Population) FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English');	world_1
SELECT SUM(T1.Population) FROM country AS T1 LEFT JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language != 'English' OR T2.Language IS NULL;	world_1
SELECT T2.Language FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.HeadOfState = 'Beatrix' AND T2.IsOfficial = 'T';	world_1
SELECT cl.Language FROM countrylanguage cl JOIN country c ON cl.CountryCode = c.Code WHERE c.HeadOfState = 'Beatrix' AND cl.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT T2.Language) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.IndepYear <1930 AND T2.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT T2.Language) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.IndepYear <1930 AND T2.IsOfficial = 'T';	world_1
SELECT Name FROM country WHERE SurfaceArea > (SELECT MAX(SurfaceArea) FROM country WHERE Continent = 'Europe')	world_1
SELECT Name FROM country WHERE SurfaceArea > (SELECT MAX(SurfaceArea) FROM country WHERE Continent = 'Europe')	world_1
SELECT Name FROM country WHERE Continent = 'Africa' AND Population < (SELECT MIN(Population) FROM country WHERE Continent = 'Asia');	world_1
SELECT c.Name FROM country c WHERE c.Continent = 'Africa' AND c.Population < (SELECT MIN(Population) FROM country WHERE Continent = 'Asia');	world_1
SELECT Name FROM country WHERE Continent = 'Asia' AND Population > (SELECT MAX(Population) FROM country WHERE Continent = 'Africa')	world_1
SELECT Name FROM country WHERE Continent = 'Asia' AND Population > (SELECT MAX(Population) FROM country WHERE Continent = 'Africa')	world_1
SELECT Code FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' );	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English')	world_1
SELECT DISTINCT CountryCode FROM countrylanguage WHERE Language != 'English';	world_1
SELECT DISTINCT CountryCode FROM countrylanguage WHERE Language != 'English';	world_1
SELECT Code FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' ) AND GovernmentForm != 'Republic';	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English') AND GovernmentForm != 'Republic';	world_1
SELECT c.Name FROM city AS c JOIN country AS co ON c.CountryCode = co.Code JOIN countrylanguage AS cl ON co.Code = cl.CountryCode WHERE co.Continent = 'Europe' AND cl.Language = 'English' AND cl.IsOfficial = 'F';	world_1
SELECT c.Name FROM city c JOIN country co ON c.CountryCode = co.Code LEFT JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode AND cl.Language = 'English' WHERE co.Continent = 'Europe' AND (cl.IsOfficial = 'F' OR cl.Language IS NULL);	world_1
SELECT DISTINCT T1.Name FROM city AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code JOIN countrylanguage AS T3 ON T2.Code = T3.CountryCode WHERE T2.Continent = 'Asia' AND T3.Language = 'Chinese' AND T3.IsOfficial = 'T';	world_1
SELECT DISTINCT c.Name FROM city c JOIN country co ON c.CountryCode = co.Code JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode WHERE co.Continent = 'Asia' AND cl.Language = 'Chinese' AND cl.IsOfficial = 'T';	world_1
SELECT Name, IndepYear, SurfaceArea FROM country ORDER BY Population ASC LIMIT 1;	world_1
SELECT Name, IndepYear, SurfaceArea FROM country ORDER BY Population ASC LIMIT 1;	world_1
SELECT T1.Population, T1.Name, T1.HeadOfState FROM country AS T1 ORDER BY T1.SurfaceArea DESC LIMIT 1;	world_1
SELECT T1.Name, T1.Population, T1.HeadOfState FROM country AS T1 WHERE T1.SurfaceArea = (SELECT MAX(SurfaceArea) FROM country);	world_1
SELECT c.Name, COUNT(cl.Language) AS NumberOfLanguages FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode GROUP BY c.Name HAVING COUNT(cl.Language) >= 3;	world_1
SELECT c.Name, COUNT(cl.Language) AS LanguageCount FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode GROUP BY c.Name HAVING LanguageCount > 2;	world_1
SELECT District, COUNT(*) FROM city WHERE Population > (SELECT AVG(Population) FROM city) GROUP BY District;	world_1
SELECT District, COUNT(*) FROM city WHERE Population > (SELECT AVG(Population) FROM city) GROUP BY District;	world_1
SELECT GovernmentForm, SUM(Population) AS TotalPopulation FROM country WHERE LifeExpectancy > 72 GROUP BY GovernmentForm;	world_1
SELECT c.GovernmentForm, SUM(c.Population) AS TotalPopulation FROM country c WHERE c.LifeExpectancy >72GROUP BY c.GovernmentForm;	world_1
SELECT continent, AVG(lifeexpectancy) AS average_life_expectancy, SUM(population) AS total_population FROM country GROUP BY continent HAVING AVG(lifeexpectancy) < 72;	world_1
SELECT Continent, SUM(Population) AS TotalPopulation, AVG(LifeExpectancy) AS AverageLifeExpectancy FROM country GROUP BY Continent HAVING AverageLifeExpectancy < 72;	world_1
SELECT Name, SurfaceArea FROM country ORDER BY SurfaceArea DESC LIMIT 5;	world_1
SELECT Name, SurfaceArea FROM country ORDER BY SurfaceArea DESC LIMIT 5;	world_1
SELECT Name FROM country ORDER BY Population DESC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population DESC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population ASC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population ASC LIMIT 3;	world_1
SELECT COUNT(*) FROM country WHERE Continent = 'Asia';	world_1
SELECT COUNT(*) FROM country WHERE Continent = 'Asia';	world_1
SELECT Name FROM country WHERE Continent = 'Europe' AND Population = 80000;	world_1
SELECT c.Name FROM country c JOIN city ci ON c.Code = ci.CountryCode WHERE c.Continent = 'Europe' AND ci.Population = 80000;	world_1
SELECT SUM(c.Population), AVG(c.SurfaceArea) FROM country c WHERE c.Continent = 'North America' AND c.SurfaceArea > 3000;	world_1
SELECT SUM(c.Population), AVG(c.SurfaceArea) FROM country c WHERE c.Continent = 'North America' AND c.SurfaceArea > 3000;	world_1
SELECT Name FROM city WHERE Population BETWEEN 160000 AND 900000;	world_1
SELECT Name FROM city WHERE Population BETWEEN 160000 AND 900000;	world_1
SELECT Language FROM countrylanguage GROUP BY Language ORDER BY COUNT(DISTINCT CountryCode) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage GROUP BY Language ORDER BY COUNT(DISTINCT CountryCode) DESC LIMIT 1;	world_1
SELECT c.Name AS CountryName, cl.Language, cl.Percentage FROM country c JOIN ( SELECT CountryCode, MAX(Percentage) AS MaxPercentage FROM countrylanguage GROUP BY CountryCode ) max_cl ON c.Code = max_cl.CountryCode JOIN countrylanguage cl ON cl.CountryCode = max_cl.CountryCode AND cl.Percentage = max_cl.MaxPercentage;	world_1
SELECT country.Code, countrylanguage.Language FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode WHERE countrylanguage.Percentage = ( SELECT MAX(Percentage) FROM countrylanguage AS cl WHERE cl.CountryCode = country.Code );	world_1
SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'Spanish' AND T2.Percentage = ( SELECT MAX(Percentage) FROM countrylanguage WHERE Language = 'Spanish' );	world_1
SELECT COUNT(DISTINCT cl.CountryCode) FROM countrylanguage cl WHERE cl.Language = 'Spanish' AND cl.IsOfficial = 'T';	world_1
SELECT CountryCode FROM countrylanguage WHERE Language = 'Spanish' ORDER BY Percentage DESC LIMIT 1;	world_1
SELECT CountryCode FROM countrylanguage WHERE Language = 'Spanish' AND IsOfficial = 'T';	world_1
SELECT COUNT(*) FROM conductor;	orchestra
SELECT COUNT(*) FROM conductor;	orchestra
SELECT Name FROM conductor ORDER BY Age ASC;	orchestra
SELECT Name FROM conductor ORDER BY Age;	orchestra
SELECT Name FROM conductor WHERE Nationality != 'USA';	orchestra
SELECT T2.Name FROM orchestra AS T1 JOIN conductor AS T2 ON T1.Conductor_ID = T2.Conductor_ID WHERE T2.Nationality != 'USA';	orchestra
SELECT Record_Company FROM orchestra ORDER BY Year_of_Founded DESC;	orchestra
SELECT Record_Company FROM orchestra ORDER BY Year_of_Founded DESC;	orchestra
SELECT AVG(Attendance) FROM show WHERE Result = 'T';	orchestra
SELECT AVG(Attendance) FROM show WHERE Result = 'T';	orchestra
SELECT max(Share), min(Share) FROM performance WHERE Type != 'Live final';	orchestra
SELECT max(Share) , min(Share) FROM performance WHERE Type != 'Live final';	orchestra
SELECT COUNT(DISTINCT Nationality) FROM conductor;	orchestra
SELECT COUNT(DISTINCT Nationality) FROM conductor;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC;	orchestra
SELECT T4.Name FROM show AS T1 JOIN performance AS T2 ON T1.Performance_ID = T2.Performance_ID JOIN orchestra AS T3 ON T2.Orchestra_ID = T3.Orchestra_ID JOIN conductor AS T4 ON T3.Conductor_ID = T4.Conductor_ID WHERE T1.Result = 'T' ORDER BY T4.Year_of_Work DESC LIMIT 1;	orchestra
SELECT T4.Name FROM show AS T1 JOIN performance AS T2 ON T1.Performance_ID = T2.Performance_ID JOIN orchestra AS T3 ON T2.Orchestra_ID = T3.Orchestra_ID JOIN conductor AS T4 ON T3.Conductor_ID = T4.Conductor_ID WHERE T1.Result = 'T' GROUP BY T4.Conductor_ID ORDER BY COUNT(*) DESC LIMIT 1;	orchestra
SELECT conductor.Name, orchestra.Orchestra FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID JOIN performance ON orchestra.Orchestra_ID = performance.Orchestra_ID JOIN show ON performance.Performance_ID = show.Performance_ID WHERE show.Result = 'T';	orchestra
SELECT conductor.Name, orchestra.Orchestra FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID HAVING COUNT(DISTINCT o.Orchestra_ID) > 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID HAVING COUNT(DISTINCT o.Orchestra_ID) > 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID JOIN performance p ON o.Orchestra_ID = p.Orchestra_ID JOIN show s ON p.Performance_ID = s.Performance_ID WHERE s.Result = 'T' GROUP BY c.Name ORDER BY COUNT(DISTINCT o.Orchestra_ID) DESC LIMIT 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID JOIN performance p ON o.Orchestra_ID = p.Orchestra_ID JOIN show s ON p.Performance_ID = s.Performance_ID WHERE s.Result = 'T' GROUP BY c.Name ORDER BY COUNT(DISTINCT o.Orchestra_ID) DESC LIMIT 1;	orchestra
SELECT DISTINCT T3.Name FROM orchestra AS T1 JOIN performance AS T2 ON T1.Orchestra_ID = T2.Orchestra_ID JOIN conductor AS T3 ON T1.Conductor_ID = T3.Conductor_ID WHERE T1.Year_of_Founded > 2008;	orchestra
SELECT conductor.Name FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID JOIN performance ON orchestra.Orchestra_ID = performance.Orchestra_ID JOIN show ON performance.Performance_ID = show.Performance_ID WHERE orchestra.Year_of_Founded > 2008 AND show.Result = 'T';	orchestra
SELECT Record_Company, COUNT(*) FROM orchestra GROUP BY Record_Company;	orchestra
SELECT Record_Company, COUNT(*) AS NumberOfOrchestras FROM orchestra GROUP BY Record_Company;	orchestra
SELECT Major_Record_Format FROM orchestra GROUP BY Major_Record_Format ORDER BY COUNT(*) ASC;	orchestra
SELECT Major_Record_Format FROM orchestra WHERE Orchestra_ID IN ( SELECT Orchestra_ID FROM performance WHERE Performance_ID IN ( SELECT Performance_ID FROM show WHERE Result = 'T' ) ) GROUP BY Major_Record_Format ORDER BY COUNT(*) DESC;	orchestra
SELECT Record_Company FROM orchestra GROUP BY Record_Company ORDER BY COUNT(*) DESC LIMIT 1;	orchestra
SELECT Record_Company FROM orchestra GROUP BY Record_Company ORDER BY COUNT(*) DESC LIMIT 1;	orchestra
SELECT Orchestra FROM orchestra WHERE Orchestra_ID NOT IN (SELECT Orchestra_ID FROM performance)	orchestra
SELECT Orchestra FROM orchestra WHERE Orchestra_ID NOT IN (SELECT Orchestra_ID FROM performance)	orchestra
SELECT Record_Company FROM orchestra WHERE Year_of_Founded <2003 INTERSECT SELECT Record_Company FROM orchestra WHERE Year_of_Founded > 2003;	orchestra
SELECT Record_Company FROM orchestra WHERE Year_of_Founded <2003 INTERSECT SELECT Record_Company FROM orchestra WHERE Year_of_Founded > 2003;	orchestra
SELECT COUNT(*) FROM orchestra WHERE Major_Record_Format IN ('CD', 'DVD');	orchestra
SELECT COUNT(*) FROM orchestra WHERE Major_Record_Format IN ('CD', 'DVD');	orchestra
SELECT DISTINCT o.Year_of_Founded FROM orchestra o JOIN performance p ON o.Orchestra_ID = p.Orchestra_ID GROUP BY o.Orchestra_ID HAVING COUNT(p.Performance_ID) > 1;	orchestra
SELECT DISTINCT o.Year_of_Founded FROM orchestra o JOIN performance p ON o.Orchestra_ID = p.Orchestra_ID GROUP BY o.Orchestra_ID HAVING COUNT(p.Performance_ID) > 1;	orchestra
SELECT COUNT(*) FROM Highschooler;	network_1
SELECT count(*) FROM Highschooler;	network_1
SELECT name, grade FROM Highschooler;	network_1
SELECT name, grade FROM Highschooler;	network_1
SELECT DISTINCT grade FROM Highschooler;	network_1
SELECT grade FROM Highschooler;	network_1
SELECT grade FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT grade FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT name FROM Highschooler WHERE grade = 10;	network_1
SELECT name FROM Highschooler WHERE grade = 10;	network_1
SELECT ID FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT ID FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT COUNT(*) FROM Highschooler WHERE grade IN (9, 10);	network_1
SELECT count(*) FROM Highschooler WHERE grade = 9 OR grade = 10;	network_1
SELECT grade, COUNT(*) FROM Highschooler GROUP BY grade;	network_1
SELECT grade, COUNT(*) FROM Highschooler GROUP BY grade;	network_1
SELECT grade FROM Highschooler GROUP BY grade ORDER BY COUNT(*) DESC LIMIT 1;	network_1
SELECT grade FROM Highschooler GROUP BY grade ORDER BY count(*) DESC LIMIT 1;	network_1
SELECT grade FROM Highschooler GROUP BY grade HAVING COUNT(*) >= 4;	network_1
SELECT grade FROM Highschooler GROUP BY grade HAVING COUNT(*) >= 4;	network_1
SELECT student_id, COUNT(friend_id) AS number_of_friends FROM Friend GROUP BY student_id;	network_1
SELECT student_id, COUNT(friend_id) AS friend_count FROM Friend GROUP BY student_id;	network_1
SELECT T1.name, COUNT(T2.friend_id) AS num_friends FROM Highschooler AS T1 LEFT JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T1.name, COUNT(T2.friend_id) AS num_friends FROM Highschooler AS T1 LEFT JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T2.student_id ORDER BY count(T2.friend_id) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID ORDER BY COUNT(T2.friend_id) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 3;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 3;	network_1
SELECT T3.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Highschooler AS T3 ON T2.friend_id = T3.ID WHERE T1.name = 'Kyle'	network_1
SELECT T3.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Highschooler AS T3 ON T2.friend_id = T3.ID WHERE T1.name = 'Kyle';	network_1
SELECT COUNT(friend_id) FROM Friend WHERE student_id = (SELECT ID FROM Highschooler WHERE name = 'Kyle')	network_1
SELECT COUNT(friend_id) FROM Friend WHERE student_id = (SELECT ID FROM Highschooler WHERE name = 'Kyle');	network_1
SELECT ID FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend);	network_1
SELECT ID FROM Highschooler EXCEPT SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend;	network_1
SELECT name FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend)	network_1
SELECT name FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend);	network_1
SELECT ID FROM Highschooler WHERE ID IN (SELECT student_id FROM Friend) INTERSECT SELECT ID FROM Highschooler WHERE ID IN (SELECT liked_id FROM Likes)	network_1
SELECT student_id FROM Friend INTERSECT SELECT student_id FROM Likes;	network_1
SELECT DISTINCT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Likes AS T3 ON T1.ID = T3.liked_id;	network_1
SELECT DISTINCT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Likes AS T3 ON T1.ID = T3.liked_id;	network_1
SELECT student_id, COUNT(liked_id) AS like_count FROM Likes GROUP BY student_id;	network_1
SELECT student_id, COUNT(liked_id) AS like_count FROM Likes GROUP BY student_id;	network_1
SELECT T1.name, COUNT(T2.liked_id) AS number_of_likes FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T1.name, COUNT(T2.student_id) AS like_count FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.liked_id GROUP BY T1.ID, T1.name;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.liked_id GROUP BY T2.liked_id ORDER BY count(*) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID ORDER BY COUNT(T2.liked_id) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID HAVING COUNT(T2.liked_id) >= 2;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.liked_id GROUP BY T1.ID HAVING COUNT(T2.student_id) >= 2;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id WHERE T1.grade >5 GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 2;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id WHERE T1.grade >5 GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 2;	network_1
SELECT COUNT(*) FROM Likes AS L JOIN Highschooler AS H ON L.student_id = H.ID WHERE H.name = 'Kyle';	network_1
SELECT COUNT(*) FROM Likes WHERE liked_id = (SELECT ID FROM Highschooler WHERE name = 'Kyle');	network_1
SELECT AVG(grade) FROM Highschooler WHERE ID IN (SELECT student_id FROM Friend)	network_1
SELECT AVG(grade) FROM Highschooler WHERE ID IN (SELECT student_id FROM Friend)	network_1
SELECT MIN(grade) FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend);	network_1
SELECT MIN(grade) FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend)	network_1
SELECT state FROM Owners INTERSECT SELECT state FROM Professionals;	dog_kennels
SELECT state FROM Owners INTERSECT SELECT state FROM Professionals;	dog_kennels
SELECT AVG(dogs.age) FROM dogs JOIN treatments ON dogs.dog_id = treatments.dog_id;	dog_kennels
SELECT AVG(dogs.age) FROM dogs JOIN treatments ON dogs.dog_id = treatments.dog_id;	dog_kennels
SELECT DISTINCT p.professional_id, p.last_name, p.cell_number FROM Professionals p WHERE p.state = 'Indiana' OR p.professional_id IN ( SELECT t.professional_id FROM Treatments t GROUP BY t.professional_id HAVING COUNT(t.treatment_id) > 2 );	dog_kennels
SELECT P.professional_id, P.last_name, P.cell_number FROM Professionals P WHERE P.state = 'Indiana' OR P.professional_id IN ( SELECT T.professional_id FROM Treatments T GROUP BY T.professional_id HAVING COUNT(T.treatment_id) > 2 );	dog_kennels
SELECT d.name FROM Dogs d WHERE d.dog_id NOT IN ( SELECT t.dog_id FROM Treatments t GROUP BY t.dog_id HAVING SUM(t.cost_of_treatment) > 1000 );	dog_kennels
SELECT Dogs.name FROM Dogs JOIN Treatments ON Dogs.dog_id = Treatments.dog_id WHERE Dogs.owner_id NOT IN ( SELECT owner_id FROM Dogs JOIN Treatments ON Dogs.dog_id = Treatments.dog_id GROUP BY owner_id HAVING SUM(Treatments.cost_of_treatment) > 1000 );	dog_kennels
SELECT first_name FROM Professionals UNION SELECT first_name FROM Owners EXCEPT SELECT name FROM Dogs	dog_kennels
SELECT first_name FROM Professionals UNION SELECT first_name FROM Owners EXCEPT SELECT name FROM Dogs	dog_kennels
SELECT professional_id, role_code, email_address FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT professional_id, role_code, email_address FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT O.owner_id, O.first_name, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id GROUP BY O.owner_id, O.first_name, O.last_name ORDER BY COUNT(D.dog_id) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.first_name, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id GROUP BY O.owner_id, O.first_name, O.last_name ORDER BY COUNT(D.dog_id) DESC LIMIT 1;	dog_kennels
SELECT T1.professional_id, T1.role_code, T1.first_name FROM Professionals AS T1 JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id GROUP BY T1.professional_id HAVING COUNT(T2.treatment_id) >= 2;	dog_kennels
SELECT P.professional_id, P.role_code, P.first_name FROM Professionals P JOIN Treatments T ON P.professional_id = T.professional_id GROUP BY P.professional_id, P.role_code, P.first_name HAVING COUNT(T.treatment_id) >= 2;	dog_kennels
SELECT B.breed_name FROM Breeds B JOIN Dogs D ON B.breed_code = D.breed_code GROUP BY B.breed_name ORDER BY COUNT(*) DESC LIMIT 1;	dog_kennels
SELECT B.breed_name FROM Dogs D JOIN Breeds B ON D.breed_code = B.breed_code GROUP BY B.breed_name ORDER BY COUNT(*) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Treatments T ON D.dog_id = T.dog_id WHERE O.first_name = 'Tre' GROUP BY O.owner_id, O.last_name ORDER BY COUNT(T.treatment_id) DESC LIMIT 1;	dog_kennels
SELECT o.owner_id, o.last_name FROM Owners o JOIN Dogs d ON o.owner_id = d.owner_id JOIN Treatments t ON d.dog_id = t.dog_id WHERE o.first_name = 'Tre' GROUP BY o.owner_id, o.last_name ORDER BY SUM(t.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT Treatment_Types.treatment_type_description FROM Treatments JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code GROUP BY Treatments.treatment_type_code ORDER BY SUM(Treatments.cost_of_treatment) ASC LIMIT 1;	dog_kennels
SELECT Treatment_Types.treatment_type_description FROM Treatments JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code GROUP BY Treatments.treatment_type_code ORDER BY SUM(Treatments.cost_of_treatment) ASC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.zip_code FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Treatments T ON D.dog_id = T.dog_id GROUP BY O.owner_id, O.zip_code ORDER BY SUM(T.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT T1.owner_id, T1.zip_code FROM Owners AS T1 JOIN Dogs AS T2 ON T1.owner_id = T2.owner_id JOIN Treatments AS T3 ON T2.dog_id = T3.dog_id GROUP BY T1.owner_id, T1.zip_code ORDER BY SUM(T3.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT T1.professional_id, T1.cell_number FROM Professionals AS T1 JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id GROUP BY T1.professional_id HAVING COUNT(DISTINCT T2.treatment_type_code) >= 2;	dog_kennels
SELECT T1.professional_id, T1.cell_number FROM Professionals AS T1 JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id GROUP BY T1.professional_id HAVING COUNT(DISTINCT T2.treatment_type_code) >= 2;	dog_kennels
SELECT Professionals.first_name, Professionals.last_name FROM Professionals JOIN Treatments ON Professionals.professional_id = Treatments.professional_id WHERE Treatments.cost_of_treatment < (SELECT AVG(cost_of_treatment) FROM Treatments);	dog_kennels
SELECT DISTINCT P.first_name, P.last_name FROM Professionals P JOIN Treatments T ON P.professional_id = T.professional_id WHERE T.cost_of_treatment < (SELECT AVG(cost_of_treatment) FROM Treatments);	dog_kennels
SELECT T1.date_of_treatment, T2.first_name FROM Treatments AS T1 JOIN Professionals AS T2 ON T1.professional_id = T2.professional_id;	dog_kennels
SELECT T.date_of_treatment, P.first_name FROM Treatments T JOIN Professionals P ON T.professional_id = P.professional_id;	dog_kennels
SELECT T2.cost_of_treatment, T1.treatment_type_description FROM Treatment_Types AS T1 JOIN Treatments AS T2 ON T1.treatment_type_code = T2.treatment_type_code;	dog_kennels
SELECT T2.cost_of_treatment, T1.treatment_type_description FROM Treatment_Types AS T1 JOIN Treatments AS T2 ON T1.treatment_type_code = T2.treatment_type_code;	dog_kennels
SELECT O.first_name, O.last_name, S.size_description FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Sizes S ON D.size_code = S.size_code;	dog_kennels
SELECT O.first_name, O.last_name, S.size_description FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Sizes S ON D.size_code = S.size_code;	dog_kennels
SELECT Owners.first_name, Dogs.name FROM Owners JOIN Dogs ON Owners.owner_id = Dogs.owner_id;	dog_kennels
SELECT Owners.first_name, Dogs.name FROM Owners JOIN Dogs ON Owners.owner_id = Dogs.owner_id;	dog_kennels
SELECT D.name, T.date_of_treatment FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id WHERE D.breed_code = ( SELECT breed_code FROM Dogs GROUP BY breed_code ORDER BY COUNT(*) ASC LIMIT 1 );	dog_kennels
SELECT D.name, T.date_of_treatment FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id WHERE D.breed_code = ( SELECT breed_code FROM Dogs GROUP BY breed_code ORDER BY COUNT(*) ASC LIMIT 1 );	dog_kennels
SELECT O.first_name, D.name FROM Owners AS O JOIN Dogs AS D ON O.owner_id = D.owner_id WHERE O.state = 'Virginia';	dog_kennels
SELECT Owners.first_name, Dogs.name FROM Owners JOIN Dogs ON Owners.owner_id = Dogs.owner_id WHERE Owners.state = 'Virginia';	dog_kennels
SELECT D.date_arrived, D.date_departed FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id;	dog_kennels
SELECT Dogs.date_arrived, Dogs.date_departed FROM Dogs JOIN Treatments ON Dogs.dog_id = Treatments.dog_id;	dog_kennels
SELECT O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id ORDER BY D.date_of_birth DESC LIMIT 1;	dog_kennels
SELECT O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id ORDER BY D.date_of_birth DESC LIMIT 1;	dog_kennels
SELECT email_address FROM Professionals WHERE state = 'Hawaii' OR state = 'Wisconsin';	dog_kennels
SELECT email_address FROM Professionals WHERE state = 'Hawaii' OR state = 'Wisconsin';	dog_kennels
SELECT date_arrived, date_departed FROM Dogs;	dog_kennels
SELECT date_arrived, date_departed FROM Dogs;	dog_kennels
SELECT COUNT(DISTINCT dog_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT dog_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT professional_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT professional_id) FROM Treatments;	dog_kennels
SELECT role_code, street, city, state FROM Professionals WHERE city LIKE '%West%';	dog_kennels
SELECT role_code, street, city, state FROM Professionals WHERE city LIKE '%West%';	dog_kennels
SELECT first_name, last_name, email_address FROM Owners WHERE state LIKE '%North%';	dog_kennels
SELECT first_name, last_name, email_address FROM Owners WHERE state LIKE '%North%';	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE age < (SELECT AVG(age) FROM Dogs);	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE age < (SELECT AVG(age) FROM Dogs);	dog_kennels
SELECT cost_of_treatment FROM Treatments ORDER BY date_of_treatment DESC LIMIT 1;	dog_kennels
SELECT cost_of_treatment FROM Treatments ORDER BY date_of_treatment DESC LIMIT 1;	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE dog_id NOT IN (SELECT dog_id FROM Treatments);	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE dog_id NOT IN (SELECT dog_id FROM Treatments);	dog_kennels
SELECT COUNT(owner_id) FROM Owners WHERE owner_id NOT IN (SELECT owner_id FROM Dogs);	dog_kennels
SELECT COUNT(owner_id) FROM Owners WHERE owner_id NOT IN (SELECT owner_id FROM Dogs);	dog_kennels
SELECT COUNT(*) FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT COUNT(*) FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT name, age, weight FROM Dogs WHERE abandoned_yn = 1;	dog_kennels
SELECT name, age, weight FROM Dogs WHERE abandoned_yn = 1;	dog_kennels
SELECT AVG(age) FROM Dogs;	dog_kennels
SELECT AVG(age) FROM Dogs;	dog_kennels
SELECT MAX(age) FROM Dogs;	dog_kennels
SELECT age FROM Dogs ORDER BY date_of_birth ASC LIMIT 1;	dog_kennels
SELECT charge_type, charge_amount FROM Charges;	dog_kennels
SELECT charge_type, charge_amount FROM Charges;	dog_kennels
SELECT charge_amount FROM Charges ORDER BY charge_amount DESC LIMIT 1;	dog_kennels
SELECT charge_amount FROM Charges WHERE charge_type = (SELECT charge_type FROM Charges ORDER BY charge_amount DESC LIMIT 1) LIMIT 1;	dog_kennels
SELECT email_address, cell_number, home_phone FROM Professionals;	dog_kennels
SELECT email_address, cell_number, home_phone FROM Professionals;	dog_kennels
SELECT DISTINCT breed_code, size_code FROM Dogs;	dog_kennels
SELECT DISTINCT breed_code, size_code FROM Dogs;	dog_kennels
SELECT Professionals.first_name, Treatment_Types.treatment_type_description FROM Professionals JOIN Treatments ON Professionals.professional_id = Treatments.professional_id JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code;	dog_kennels
SELECT Professionals.first_name, Treatment_Types.treatment_type_description FROM Professionals JOIN Treatments ON Professionals.professional_id = Treatments.professional_id JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code;	dog_kennels
SELECT COUNT(*) FROM singer;	singer
SELECT COUNT(*) FROM singer;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions ASC;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions ASC;	singer
SELECT Birth_Year, Citizenship FROM singer;	singer
SELECT Birth_Year, Citizenship FROM singer;	singer
SELECT Name FROM singer WHERE Citizenship != "France";	singer
SELECT Name FROM singer WHERE Citizenship != "French";	singer
SELECT Name FROM singer WHERE Birth_Year IN (1948, 1949);	singer
SELECT Name FROM singer WHERE Birth_Year IN (1948, 1949);	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions DESC LIMIT 1;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions DESC LIMIT 1;	singer
SELECT Citizenship, COUNT(*) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship, COUNT(*) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship FROM singer GROUP BY Citizenship ORDER BY COUNT(*) DESC LIMIT 1;	singer
SELECT Citizenship FROM singer GROUP BY Citizenship ORDER BY COUNT(*) DESC LIMIT 1;	singer
SELECT Citizenship, MAX(Net_Worth_Millions) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship, MAX(Net_Worth_Millions) AS Max_Net_Worth FROM singer GROUP BY Citizenship;	singer
SELECT T2.Title, T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID;	singer
SELECT song.Title, singer.Name FROM song JOIN singer ON song.Singer_ID = singer.Singer_ID;	singer
SELECT DISTINCT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID WHERE T2.Sales > 300000;	singer
SELECT DISTINCT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID WHERE T2.Sales > 300000;	singer
SELECT Name FROM singer WHERE Singer_ID IN (SELECT Singer_ID FROM song GROUP BY Singer_ID HAVING COUNT(*) > 1)	singer
SELECT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Singer_ID HAVING COUNT(T2.Song_ID) > 1;	singer
SELECT T1.Name, SUM(T2.Sales) AS Total_Sales FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Name;	singer
SELECT s.Name, SUM(so.Sales) AS Total_Sales FROM singer s JOIN song so ON s.Singer_ID = so.Singer_ID GROUP BY s.Name;	singer
SELECT Name FROM singer WHERE Singer_ID NOT IN (SELECT Singer_ID FROM song)	singer
SELECT Name FROM singer WHERE Singer_ID NOT IN (SELECT Singer_ID FROM song)	singer
SELECT Citizenship FROM singer WHERE Birth_Year <1945 INTERSECT SELECT Citizenship FROM singer WHERE Birth_Year > 1955;	singer
SELECT Citizenship FROM singer WHERE Birth_Year <1945 INTERSECT SELECT Citizenship FROM singer WHERE Birth_Year > 1955;	singer
SELECT COUNT(*) FROM Other_Available_Features;	real_estate_properties
SELECT T2.feature_type_name FROM Other_Available_Features AS T1 JOIN Ref_Feature_Types AS T2 ON T1.feature_type_code = T2.feature_type_code WHERE T1.feature_name = 'AirCon';	real_estate_properties
SELECT T2.property_type_description FROM Properties AS T1 JOIN Ref_Property_Types AS T2 ON T1.property_type_code = T2.property_type_code;	real_estate_properties
SELECT property_name FROM Properties WHERE property_type_code IN ('House', 'Apartment') AND room_count > 1;	real_estate_properties
